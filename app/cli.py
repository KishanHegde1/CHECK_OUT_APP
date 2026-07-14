"""Interactive administrative bootstrap commands."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.admin import Admin
from app.models.enums import UserRole
from app.models.user import User


def _required_input(label: str) -> str:
    """Prompt until a non-empty value is supplied."""

    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} is required.")


def create_admin() -> int:
    """Interactively provision the first administrator account."""

    username = _required_input("Username").lower()
    email = _required_input("Email").lower()
    admin_id = _required_input("Admin ID")
    full_name = _required_input("Full name")
    phone = _required_input("Phone")
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    with SessionLocal() as db:
        existing_user = db.scalar(
            select(User).where(or_(User.username == username, User.email == email))
        )
        if existing_user is not None:
            print(
                "A user with that username or email already exists.",
                file=sys.stderr,
            )
            return 1

        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=UserRole.ADMIN,
        )
        user.admin = Admin(
            admin_id=admin_id,
            full_name=full_name,
            phone=phone,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print(
                "The admin ID, username, or email is already in use.",
                file=sys.stderr,
            )
            return 1

    print(f"Administrator {username!r} created successfully.")
    return 0


def main() -> int:
    """Parse and execute a bootstrap command."""

    parser = argparse.ArgumentParser(description="Hostel Checkout administration")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("create-admin", help="provision an administrator")
    arguments = parser.parse_args()

    if arguments.command == "create-admin":
        return create_admin()
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
