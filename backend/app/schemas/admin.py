from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FareRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lot_id: int = Field(gt=0)
    rule_name: str = Field(min_length=1, max_length=100)
    base_rate: float = Field(gt=0)
    min_occupancy: float = Field(ge=0, le=100)
    max_occupancy: float = Field(ge=0, le=100)
    occupancy_multiplier: float = Field(gt=0)
    peak_multiplier: float = Field(default=1, gt=0)
    start_time: time | None = None
    end_time: time | None = None
    @model_validator(mode="after")
    def validate_rule(self):
        if self.min_occupancy > self.max_occupancy:
            raise ValueError("min_occupancy must not exceed max_occupancy")
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time and end_time must be provided together")
        return self


class FareRuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=100)
    base_rate: float | None = Field(default=None, gt=0)
    min_occupancy: float | None = Field(default=None, ge=0, le=100)
    max_occupancy: float | None = Field(default=None, ge=0, le=100)
    occupancy_multiplier: float | None = Field(default=None, gt=0)
    peak_multiplier: float | None = Field(default=None, gt=0)
    start_time: time | None = None
    end_time: time | None = None
    active: bool | None = None

    @field_validator(
        "rule_name",
        "base_rate",
        "min_occupancy",
        "max_occupancy",
        "occupancy_multiplier",
        "peak_multiplier",
        "active",
    )
    @classmethod
    def reject_null_values(cls, value):
        if value is None:
            raise ValueError("This fare-rule field cannot be null")
        return value


class UserAdminView(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    created_at: datetime | None
    mfa_enabled: bool


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)


class PasswordResetComplete(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class MfaCode(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaLoginVerify(MfaCode):
    challenge_token: str = Field(min_length=32, max_length=256)


class MfaResend(BaseModel):
    challenge_token: str = Field(min_length=32, max_length=256)


class MfaDisable(MfaLoginVerify):
    current_password: str = Field(min_length=1)
