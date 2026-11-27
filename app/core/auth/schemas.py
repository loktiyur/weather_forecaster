import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.language import Language
from app.core.units import Units


class LoginRequest(BaseModel):
    email: EmailStr = Field(examples=["anna@example.com"])
    password: str = Field(min_length=1, max_length=128, examples=["correct horse battery"])

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()


MIN_PASSWORD_LENGTH = 8


class RegisterRequest(LoginRequest):
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH, max_length=128, examples=["correct horse battery"]
    )

    @field_validator("password")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # Spaces at the start or end do not count towards the length ("        " is no
        # password), but the password is stored exactly as typed: never stripped, so the
        # same input always logs in. Spaces inside a passphrase count as usual.
        if len(value.strip()) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"must have at least {MIN_PASSWORD_LENGTH} characters "
                "besides spaces at the start or end"
            )
        return value


class Preferences(BaseModel):
    """What the user chose; `null`: not chosen, the app's default applies.

    Stored in `auth.users.preferences` (JSONB) with only the chosen fields, so a changed
    default reaches everyone who never chose.
    """

    units: Units | None = Field(
        default=None, description="Used by the weather endpoints when `units` is not given"
    )
    language: Language | None = Field(default=None, description="Interface language")


class PreferencesUpdate(Preferences):
    """Only the fields sent change; `null` removes a choice. Unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")


class UserResponse(BaseModel):
    """The logged-in user. Never contains the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str = Field(examples=["anna@example.com"])
    created_at: dt.datetime
    preferences: Preferences
