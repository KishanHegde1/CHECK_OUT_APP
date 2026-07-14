"""FastAPI application factory and process entry point."""

from __future__ import annotations

import logging
import uuid
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import Settings, get_settings
from app.core.dependencies import DatabaseSession
from app.core.exceptions import APIError
from app.routes import admin, auth, notification, security, student
from app.schemas.common import ErrorResponse
from app.utils.response import json_error_response, json_success_response

logger = logging.getLogger(__name__)


ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Authentication required"},
    403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    405: {"model": ErrorResponse, "description": "Method not allowed"},
    409: {"model": ErrorResponse, "description": "Resource conflict"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
    503: {"model": ErrorResponse, "description": "Database unavailable"},
}


def _validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    """Convert FastAPI validation details into the standard error contract."""

    errors: list[dict[str, str]] = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
        errors.append(
            {
                "field": location or "request",
                "message": str(item.get("msg", "Invalid value")),
                "code": str(item.get("type", "validation_error")),
            }
        )
    return errors


def _add_security_headers(response: JSONResponse, *, production: bool) -> None:
    """Set headers that are safe for this JSON API and Flutter Web clients."""

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=()")
    if production:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )


def create_application(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title=runtime_settings.app_name,
        version="1.0.0",
        debug=runtime_settings.debug,
        responses=ERROR_RESPONSES,
        docs_url=None if runtime_settings.app_env == "production" else "/docs",
        redoc_url=None if runtime_settings.app_env == "production" else "/redoc",
    )

    origins = runtime_settings.cors_origins
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        started_at = perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        _add_security_headers(
            response,
            production=runtime_settings.app_env == "production",
        )
        logger.info(
            "request_id=%s method=%s path=%s status_code=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (perf_counter() - started_at) * 1000,
        )
        return response

    @application.exception_handler(APIError)
    async def api_error_handler(
        _request: Request,
        exc: APIError,
    ) -> JSONResponse:
        response = json_error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return json_error_response(
            message="Request validation failed",
            errors=_validation_errors(exc),
            status_code=422,
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        response = json_error_response(
            message=str(exc.detail),
            status_code=exc.status_code,
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request,
        _exc: IntegrityError,
    ) -> JSONResponse:
        logger.warning(
            "Database integrity failure while processing %s %s",
            request.method,
            request.url.path,
        )
        return json_error_response(
            message="The request conflicts with existing data",
            status_code=409,
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        logger.warning(
            "Database failure (%s) while processing %s %s",
            type(exc).__name__,
            request.method,
            request.url.path,
        )
        return json_error_response(
            message="Database service is unavailable",
            status_code=503,
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        if runtime_settings.app_env == "production":
            logger.error(
                "Unhandled exception (%s) while processing %s %s",
                type(exc).__name__,
                request.method,
                request.url.path,
            )
        else:
            logger.exception(
                "Unhandled error while processing %s %s",
                request.method,
                request.url.path,
                exc_info=exc,
            )
        return json_error_response(
            message="Internal server error",
            status_code=500,
        )

    prefix = runtime_settings.api_prefix
    application.include_router(auth.router, prefix=prefix)
    application.include_router(student.router, prefix=prefix)
    application.include_router(security.router, prefix=prefix)
    application.include_router(admin.router, prefix=prefix)
    application.include_router(notification.router, prefix=prefix)

    @application.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return json_success_response(
            data={"status": "healthy"},
            message="Service is healthy",
        )

    def _database_health(db: DatabaseSession, *, legacy: bool) -> JSONResponse:
        """Report database reachability without disclosing connection details."""

        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.rollback()
            logger.warning("Database health check failed")
            return json_error_response(
                message="Database service is unavailable",
                status_code=503,
            )
        if legacy:
            return json_success_response(
                data={"status": "ready", "database": "reachable"},
                message="Service is ready",
            )
        return json_success_response(
            data={"status": "ok", "database": "connected"},
            message="Database is connected",
        )

    @application.get("/health/db", include_in_schema=False)
    def database_health(db: DatabaseSession) -> JSONResponse:
        """Return a database-aware health result for operators."""

        return _database_health(db, legacy=False)

    @application.get("/ready", include_in_schema=False)
    def readiness(db: DatabaseSession) -> JSONResponse:
        """Compatibility readiness endpoint retained for existing clients."""

        return _database_health(db, legacy=True)

    return application


app = create_application()
