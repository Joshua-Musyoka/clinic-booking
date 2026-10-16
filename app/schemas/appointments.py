from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class AppointmentCreate(BaseModel):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    start_at: datetime

    @field_validator("start_at")
    @classmethod
    def validate_start_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "start_at must include a timezone offset."
            )

        return value.astimezone(timezone.utc)


class AppointmentReschedule(BaseModel):
    start_at: datetime

    @field_validator("start_at")
    @classmethod
    def validate_start_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "start_at must include a timezone offset."
            )

        return value.astimezone(timezone.utc)


class AppointmentCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Cancellation reason cannot be empty."
            )

        return value