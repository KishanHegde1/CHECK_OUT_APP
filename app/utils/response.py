"""Helpers for building the API's standard JSON envelopes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.schemas.common import APIResponse, ErrorDetail, ErrorResponse

DataT = TypeVar("DataT")
ErrorItem = ErrorDetail | str | dict[str, Any]


def success_response(
    data: DataT | None = None,
    message: str = "Request successful",
) -> dict[str, Any]:
    """Return a serializable success envelope.

    A plain mapping lets FastAPI apply the response model and the status code
    configured on the route.
    """

    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_response(
    message: str,
    errors: Sequence[ErrorItem] | ErrorItem | None = None,
) -> dict[str, Any]:
    """Return a serializable failure envelope."""

    if errors is None:
        normalized_errors: list[ErrorItem] = []
    elif isinstance(errors, (str, dict, ErrorDetail)):
        normalized_errors = [errors]
    else:
        normalized_errors = list(errors)

    serialized_errors = [
        item.model_dump(mode="json") if isinstance(item, BaseModel) else item
        for item in normalized_errors
    ]
    return {
        "success": False,
        "message": message,
        "errors": serialized_errors,
    }


def json_success_response(
    data: DataT | None = None,
    message: str = "Request successful",
    status_code: int = 200,
) -> JSONResponse:
    """Return an explicit ``JSONResponse`` containing a success envelope."""

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(success_response(data=data, message=message)),
    )


def json_error_response(
    message: str,
    errors: Sequence[ErrorItem] | ErrorItem | None = None,
    status_code: int = 400,
) -> JSONResponse:
    """Return an explicit ``JSONResponse`` containing a failure envelope."""

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_response(message=message, errors=errors)),
    )


__all__ = [
    "APIResponse",
    "ErrorDetail",
    "ErrorResponse",
    "error_response",
    "json_error_response",
    "json_success_response",
    "success_response",
]
