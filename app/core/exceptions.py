"""Application exceptions consumed by the HTTP exception handlers."""

from collections.abc import Mapping, Sequence
from typing import Any


class APIError(Exception):
    """A safe, structured error intended for an API response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        errors: Sequence[Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = list(errors) if errors is not None else []
        self.headers = dict(headers) if headers is not None else None
