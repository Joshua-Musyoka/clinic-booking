from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pymysql

from app.database import database_connection, execute_procedure


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


class AppointmentServiceError(Exception):
    """An error that can be translated into an HTTP response."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


PROCEDURE_ERRORS = {
    "INVALID_DATE": (400, "A valid date is required."),
    "INVALID_START_TIME": (400, "A valid appointment start time is required."),
    "INVALID_SLOT_ALIGNMENT": (
        400,
        "Appointments must start on a 30-minute boundary.",
    ),
    "BOOKING_NOTICE_TOO_SHORT": (
        400,
        "Appointments must be booked at least 60 minutes in advance.",
    ),
    "DOCTOR_NOT_FOUND": (404, "Doctor not found."),
    "DOCTOR_INACTIVE": (409, "This doctor is currently inactive."),
    "PATIENT_NOT_FOUND": (404, "Patient not found."),
    "PATIENT_INACTIVE": (409, "This patient is currently inactive."),
    "OUTSIDE_WORKING_HOURS": (
        409,
        "The requested time is outside the doctor's working hours.",
    ),
    "SLOT_ALREADY_BOOKED": (
        409,
        "The requested appointment slot is already booked.",
    ),
    "APPOINTMENT_NOT_FOUND": (404, "Appointment not found."),
    "APPOINTMENT_ALREADY_CANCELLED": (
        409,
        "This appointment has already been cancelled.",
    ),
    "APPOINTMENT_ALREADY_COMPLETED": (
        409,
        "A completed appointment cannot be changed.",
    ),
    "CANCELLATION_REASON_REQUIRED": (
        400,
        "A cancellation reason is required.",
    ),
    "PATIENT_ID_REQUIRED": (400, "A patient ID is required."),
}


def _handle_database_error(exc: Exception) -> None:
    """Convert known MariaDB SIGNAL errors into API-friendly errors."""

    message = str(exc)

    if isinstance(exc, pymysql.MySQLError):
        for error_code, (status_code, description) in PROCEDURE_ERRORS.items():
            if error_code in message:
                raise AppointmentServiceError(
                    description,
                    status_code,
                ) from exc

    raise AppointmentServiceError(
        "A database error occurred while processing the request.",
        500,
    ) from exc


def _utc_naive(value: datetime) -> datetime:
    """
    Interpret naive datetimes as Nairobi local time, then convert to UTC.

    MariaDB DATETIME columns do not store timezone information, so the
    returned value is a naive datetime representing UTC.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=NAIROBI_TZ)

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _local_iso(value: datetime | None) -> str | None:
    """
    Convert a UTC database datetime into Nairobi local time.

    Database DATETIME values are assumed to represent UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)

    return (
        value.astimezone(NAIROBI_TZ)
        .replace(tzinfo=None)
        .isoformat(sep=" ")
    )


def _normalise_appointment(row: dict[str, Any]) -> dict[str, Any]:
    """Map database column names to the API's appointment response."""

    return {
        "appointment_id": row.get("appointment_id", row.get("id")),
        "patient_id": row.get("patient_id"),
        "doctor_id": row.get("doctor_id"),
        "start_at": _local_iso(
            row.get("start_at_utc", row.get("start_at"))
        ),
        "end_at": _local_iso(
            row.get("end_at_utc", row.get("end_at"))
        ),
        "status": row.get("status"),
    }


def get_doctor_availability(
    doctor_id: int,
    appointment_date: date,
) -> dict[str, Any]:
    """Return available appointment slots for a doctor on a given date."""

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                rows = execute_procedure(
                    cursor,
                    "sp_get_doctor_availability",
                    (doctor_id, appointment_date),
                )

        slots = [
            {
                "start_at": _local_iso(
                    row.get("start_at_utc", row.get("start_at"))
                ),
                "end_at": _local_iso(
                    row.get("end_at_utc", row.get("end_at"))
                ),
            }
            for row in rows
            if row.get("start_at_utc", row.get("start_at")) is not None
            and row.get("end_at_utc", row.get("end_at")) is not None
        ]

        return {
            "doctor_id": doctor_id,
            "date": appointment_date.isoformat(),
            "slots": slots,
        }

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)


def book_appointment(
    patient_id: int,
    doctor_id: int,
    start_at: datetime,
) -> dict[str, Any]:
    """Book an appointment using the database stored procedure."""

    start_at_utc = _utc_naive(start_at)

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                rows = execute_procedure(
                    cursor,
                    "sp_book_appointment",
                    (patient_id, doctor_id, start_at_utc),
                )

        if not rows:
            raise AppointmentServiceError(
                "The database did not return the created appointment.",
                500,
            )

        return _normalise_appointment(rows[0])

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)


def cancel_appointment(
    appointment_id: int,
    reason: str,
) -> dict[str, Any]:
    """Cancel an appointment using the database stored procedure."""

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                rows = execute_procedure(
                    cursor,
                    "sp_cancel_appointment",
                    (appointment_id, reason),
                )

        if not rows:
            raise AppointmentServiceError(
                "The database did not return the updated appointment.",
                500,
            )

        row = rows[0]

        return {
            "appointment_id": row["appointment_id"],
            "status": row["status"],
            "cancellation_reason": row["cancellation_reason"],
            "cancelled_at": _local_iso(
                row.get("cancelled_at_utc", row.get("cancelled_at"))
            ),
        }

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)


def reschedule_appointment(
    appointment_id: int,
    new_start_at: datetime,
) -> dict[str, Any]:
    """Reschedule an appointment using the database stored procedure."""

    new_start_at_utc = _utc_naive(new_start_at)

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                rows = execute_procedure(
                    cursor,
                    "sp_reschedule_appointment",
                    (appointment_id, new_start_at_utc),
                )

        if not rows:
            raise AppointmentServiceError(
                "The database did not return the rescheduled appointment.",
                500,
            )

        return _normalise_appointment(rows[0])

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)


def get_appointment(appointment_id: int) -> dict[str, Any]:
    """Retrieve a single appointment."""

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id AS appointment_id,
                        patient_id,
                        doctor_id,
                        start_at_utc,
                        end_at_utc,
                        status
                    FROM appointments
                    WHERE id = %s
                    """,
                    (appointment_id,),
                )

                row = cursor.fetchone()

        if row is None:
            raise AppointmentServiceError(
                "Appointment not found.",
                404,
            )

        return _normalise_appointment(row)

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)


def get_patient_appointments(
    patient_id: int,
    upcoming_only: bool = False,
) -> list[dict[str, Any]]:
    """Return a patient's appointments."""

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                rows = execute_procedure(
                    cursor,
                    "sp_get_patient_appointments",
                    (patient_id, upcoming_only),
                )

        return [
            {
                **_normalise_appointment(row),
                "doctor_first_name": row["doctor_first_name"],
                "doctor_last_name": row["doctor_last_name"],
                "cancellation_reason": row["cancellation_reason"],
                "cancelled_at": _local_iso(
                    row.get("cancelled_at_utc", row.get("cancelled_at"))
                ),
                "created_at": _local_iso(
                    row.get("created_at_utc", row.get("created_at"))
                ),
            }
            for row in rows
        ]

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)