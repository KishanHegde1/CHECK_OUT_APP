# Hostel Checkout API

Production-oriented FastAPI backend for the **Hostel Checkout** Flutter
application. It provides JWT authentication, role-based access for students,
administrators, and security staff, PostgreSQL persistence through SQLAlchemy
2.0, and Alembic-managed schema migrations.

## Requirements

- Python 3.12 or newer
- PostgreSQL 14 or newer
- A PostgreSQL role allowed to own the application database

## Local setup

### 1. Create the PostgreSQL database

Connect as a PostgreSQL administrator:

```sql
CREATE ROLE check_out_app WITH LOGIN PASSWORD 'replace_me';
CREATE DATABASE check_out_db OWNER check_out_app;
```

The examples below use the database URL:

```text
postgresql+psycopg://check_out_app:replace_me@localhost:5432/check_out_db
```

Percent-encode reserved URL characters if the database username or password
contains characters such as `@`, `/`, `:` or `#`.

### 2. Create and activate a virtual environment

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install the application and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure the environment

Copy `.env.example` to `.env`, then replace every placeholder:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead. The application reads:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL using the Psycopg 3 driver |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Database/readiness connection timeout |
| `SECRET_KEY` | Secret used to sign and validate JWT access tokens |
| `ALGORITHM` | JWT signing algorithm, normally `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes |
| `CORS_ORIGINS` | JSON array of explicitly trusted Flutter Web origins |

Generate a strong local secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Do not commit `.env`. Production secrets should come from the deployment
platform's secret manager rather than a file in the application image.

### 4. Apply migrations

On this Windows machine PostgreSQL 18 listens on port `2006`. To provision the
local application role/database, generate local secrets, update `.env`, and
apply migrations without putting the PostgreSQL administrator password in
shell history, run:

```powershell
.\scripts\setup_local_postgres.ps1
```

The helper prompts securely for the password chosen for PostgreSQL's
`postgres` user. It does not change `pg_hba.conf` or reset that administrator
password.

For an already provisioned database, apply migrations directly:

```bash
alembic upgrade head
```

Alembic migrations are the source of truth for the database schema. Do not
replace this step with `Base.metadata.create_all()` in deployed environments.

### 5. Run the API

For local development:

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive documentation is
served at `/docs`, with ReDoc at `/redoc` and the OpenAPI document at
`/openapi.json`.

`GET /health` is a process liveness check. `GET /ready` additionally executes a
database query and returns `503` until PostgreSQL is reachable.

## API endpoints

All application routes are under `/api`.

| Role | Method | Path | Purpose |
| --- | --- | --- | --- |
| Public | `POST` | `/api/auth/login` | Authenticate and issue an access token |
| Authenticated | `GET` | `/api/auth/me` | Return the current user |
| Authenticated | `POST` | `/api/auth/logout` | Validate and acknowledge client logout |
| Student | `GET` | `/api/student/profile` | Return the student's profile |
| Student | `GET` | `/api/student/checkouts` | List the student's checkouts |
| Student | `POST` | `/api/student/checkouts` | Create an active checkout and QR token |
| Student | `GET` | `/api/student/checkouts/active` | Return the active checkout and its stored QR token |
| Student | `GET` | `/api/student/checkouts/{checkout_id}` | Return one owned checkout |
| Security | `GET` | `/api/security/profile` | Return the security staff profile |
| Security | `POST` | `/api/security/verify-qr` | Verify a checkout QR token |
| Admin | `GET` | `/api/admin/dashboard` | Return database-backed dashboard totals |
| Admin | `GET` | `/api/admin/students` | List students |
| Admin | `POST` | `/api/admin/students` | Create a student account and profile atomically |
| Admin | `POST` | `/api/admin/students/import` | Import CSV or XLSX students in memory |
| Admin | `GET` | `/api/admin/students/{id}` | Return a student |
| Admin | `PATCH` | `/api/admin/students/{id}` | Update a student and matching login fields |
| Admin | `POST` | `/api/admin/students/{id}/deactivate` | Prevent the student from logging in |
| Admin | `POST` | `/api/admin/students/{id}/activate` | Restore the student's login access |
| Admin | `GET` | `/api/admin/checkouts` | List checkouts |
| Admin | `GET` | `/api/admin/checkouts/active` | List active checkouts |
| Admin | `GET` | `/api/admin/security-staff` | List security staff |
| Admin | `GET` | `/api/admin/notifications` | List notifications |

Except for login, protected endpoints require an access token:

```text
Authorization: Bearer <access-token>
```

Use the generated OpenAPI documentation as the authoritative request-schema
reference.

Login accepts a JSON body with `username` and `password`; the identifier may be
a username or email, and `user_id`/`userId` are accepted aliases. Checkout
creation accepts `{}` or an optional `reason`. QR verification accepts
`qr_token` and an optional `action`: `CHECKOUT` (the default) records the gate
verification, while `CHECKIN` atomically completes an active checkout and
returns the student to inside status. Completed, cancelled, and pending QR
tokens are rejected.

Administrators create student accounts with `username = full_name` and the
initial password set to `student_id`/USN. The backend hashes that password with
bcrypt before saving it; neither imports nor API responses accept or return a
password hash. Since usernames are limited to 50 characters, a full name used
for a new or updated student account must also fit that limit.

`GET /api/admin/students` keeps its existing list response and accepts optional
`search`, `department`, `year`, `room_number`, `hostel_block`, `gender`,
`hostel_status`, and `is_active` query filters. Student imports accept only
UTF-8 CSV or XLSX files up to 5 MB and 1,000 non-empty rows. Uploads are
processed in memory, and invalid rows are returned in the response without
rolling back valid rows.

## Response envelope

Successful responses use a consistent JSON envelope:

```json
{
  "success": true,
  "message": "Checkout created",
  "data": {}
}
```

Errors retain the appropriate HTTP status code and use:

```json
{
  "success": false,
  "message": "Unable to complete the request",
  "errors": []
}
```

Authentication failures return `401`, role violations return `403`, missing
resources return `404`, conflicts return `409`, and invalid input returns
`422`.

JWT access tokens are stateless unless a revocation store is configured. Clients
must delete their token after logout. Deployments that require immediate
server-side invalidation must add and enforce a token deny-list or user token
version instead of treating a successful logout response as revocation.

## Initial administrator and seed data

There is intentionally no default production password. The bootstrap entry
point is:

```bash
python -m app.cli create-admin
```

The interactive command creates the account through the application security
helpers, so its password is bcrypt-hashed and never echoed or placed in shell
history. Never put a plaintext password or shared precomputed hash in a
migration. Keep demo fixtures restricted to development and test databases.

## Migrations

After changing a SQLAlchemy model, create and review a migration:

```bash
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
alembic check
```

Review autogenerated migrations before applying them, especially enum,
constraint, index, and destructive column changes. Back up production data and
test downgrade or rollback procedures on an expendable database.

The `20260714_0002` migration creates a partial unique index allowing only one
`ACTIVE` checkout per student. Before it creates the index, it stops if existing
duplicate active rows are found. It never deletes or changes those rows; resolve
the duplicates deliberately, then rerun `alembic upgrade head`.

The `20260714_0003` migration adds `students.gender`,
`students.emergency_contact_name`, and `students.hostel_block`, plus the gender
check, hostel-block search index, and PostgreSQL `updated_at` trigger support.
It is idempotent for an already extended Neon schema: existing columns and
indexes are retained, and it does not add a second trigger that already updates
`updated_at`.

## Tests and formatting

Tests should use a dedicated migrated PostgreSQL database rather than SQLite so
foreign keys, enums, indexes, time zones, and concurrency match production.

```bash
python -m pytest
python -m pytest -m unit
python -m pytest -m integration
python -m black --check app migrations tests
python -m ruff check app migrations tests
```

To apply Black formatting locally:

```bash
python -m black app migrations tests
```

Never point the integration suite at a development or production database; test
cleanup may truncate tables and reset identities.

## Flutter integration status

The Flutter application currently uses local demo data. Its existing networking
TODOs still need to be connected to these endpoints: configure the API base URL,
send the login request in the documented schema, store the JWT in platform-secure
storage, add the `Bearer` header to protected requests, and map the standard
response envelope. The Flutter frontend is not modified by this backend project.

For Android emulators, `127.0.0.1` points at the emulator itself; the common host
alias is `10.0.2.2`. Physical devices must use an address reachable on the local
network or a deployed HTTPS API.

## Production checklist

- Generate a unique, high-entropy `SECRET_KEY` per environment and rotate it
  through a controlled process.
- Serve only through HTTPS and place Uvicorn behind a trusted reverse proxy or
  managed ingress.
- Configure an explicit CORS allow-list; never combine credentialed requests
  with a wildcard origin.
- Use a least-privilege PostgreSQL role, TLS where required, automated backups,
  and a connection limit appropriate for the number of API workers.
- Apply migrations as a separate release step before starting new workers.
- Run without `--reload`; configure worker count, timeouts, structured logs, and
  health monitoring in the deployment platform.
- Do not log passwords, access tokens, QR tokens, database URLs, or secret
  settings.
- Keep dependencies patched and run formatting, static checks, migration smoke
  tests, and the PostgreSQL integration suite in CI.
#   C H E C K _ O U T _ A P P  
 