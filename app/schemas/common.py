"""Shared Pydantic schemas used by the API surface."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class BaseSchema(BaseModel):
    """Base schema configured for request payloads and ORM responses."""

    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorDetail(BaseSchema):
    """A machine-readable error associated with an optional input field."""

    message: str = Field(min_length=1)
    field: str | None = None
    code: str | None = None


class APIResponse(BaseSchema, Generic[DataT]):
    """Standard successful API envelope."""

    success: Literal[True]
    message: str = Field(min_length=1)
    data: DataT | None


class ErrorResponse(BaseSchema):
    """Standard unsuccessful API envelope."""

    success: Literal[False]
    message: str = Field(min_length=1)
    errors: list[ErrorDetail | str | dict[str, Any]]


class PaginationMeta(BaseSchema):
    """Metadata returned with a paginated collection."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PaginatedData(BaseSchema, Generic[DataT]):
    """A typed collection and its pagination metadata."""

    items: list[DataT]
    pagination: PaginationMeta
