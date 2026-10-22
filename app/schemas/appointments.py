from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


class AppointmentCreate(BaseModel):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    start_at: datetime = Field(
        examples=["2026-10-23T10:00:00+03:00"],
        description="Appointment time in Africa/Nairobi local time (UTC+03:00).",
    )

    @field_validator("start_at")
    @classmethod
    def validate_start_at(cls, value: datetime) -> datetime:
        """Interpret timezone-naive input as Nairobi local time."""
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=NAIROBI_TZ)

        return value.astimezone(timezone.utc)


class AppointmentReschedule(BaseModel):
    start_at: datetime = Field(
        examples=["2026-10-23T10:00:00+03:00"],
        description="Appointment time in Africa/Nairobi local time (UTC+03:00).",
    )

    @field_validator("start_at")
    @classmethod
    def validate_start_at(cls, value: datetime) -> datetime:
        """Interpret timezone-naive input as Nairobi local time."""
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=NAIROBI_TZ)

        return value.astimezone(timezone.utc)


class AppointmentCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Reject empty cancellation reasons."""
        value = value.strip()

        if not value:
            raise ValueError("Cancellation reason cannot be empty.")

        return value
