from pydantic import BaseModel, Field


class FieldError(BaseModel):
    field: str = Field(examples=["city"])
    location: str = Field(description="Where the field was sent", examples=["query"])
    message: str = Field(examples=["String should have at least 1 character"])


class ErrorBody(BaseModel):
    code: str = Field(
        description="Stable, machine-readable error code", examples=["CITY_NOT_FOUND"]
    )
    message: str = Field(description="Human-readable explanation", examples=["No place found."])
    details: list[FieldError] | None = Field(
        default=None, description="Per-field problems, only for validation errors"
    )


class ErrorResponse(BaseModel):
    """The single error format used by every endpoint."""

    error: ErrorBody
