"""Deployment-safety tests that preserve the existing public API contract."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from conftest import SeedData
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app


def _error_body(response: Any, status_code: int) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["success"] is False
    assert isinstance(body["errors"], list)
    return body


def _production_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "production",
        "debug": False,
        "api_prefix": "/api",
        "cors_origins": ["https://flutter.example"],
        "database_url": (
            "postgresql://user:password@host.example/neondb?sslmode=require"
        ),
        "database_connect_timeout_seconds": 10,
        "secret_key": "a" * 32,
        "algorithm": "HS256",
        "access_token_expire_minutes": 30,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_preserve_neon_query_parameters() -> None:
    settings = _production_settings()

    assert settings.database_url == (
        "postgresql+psycopg://user:password@host.example/neondb?sslmode=require"
    )


@pytest.mark.parametrize(
    "overrides",
    (
        {"debug": True},
        {"api_prefix": "/v1"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["http://flutter.example"]},
        {"secret_key": "short"},
    ),
)
def test_production_settings_reject_unsafe_values(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _production_settings(**overrides)


def test_database_health_uses_safe_success_envelope(client: TestClient) -> None:
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Database is connected",
        "data": {"status": "ok", "database": "connected"},
    }


def test_database_health_hides_database_failures(client: TestClient) -> None:
    class UnavailableDatabase:
        def execute(self, _statement: object) -> None:
            raise SQLAlchemyError("simulated database outage")

        def rollback(self) -> None:
            return None

    original_override = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = lambda: UnavailableDatabase()
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides[get_db] = original_override

    body = _error_body(response, 503)
    assert body["message"] == "Database service is unavailable"
    assert "simulated" not in response.text


def test_expired_token_is_rejected(client: TestClient, seeded_data: SeedData) -> None:
    token = create_access_token(
        seeded_data.student_one_user.id,
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    _error_body(response, 401)


def test_inactive_account_cannot_log_in(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    seeded_data.student_one_user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "username": seeded_data.student_one_user.username,
            "password": "Correct-Horse-Battery-Staple-42",
        },
    )

    body = _error_body(response, 403)
    assert body["message"] == "User account is inactive"
