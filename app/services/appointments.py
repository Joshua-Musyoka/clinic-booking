from datetime import date, datetime, timezone
from typing import Any

import pymysql

from app.database import database_connection, execute_procedure


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

    # MariaDB SIGNAL SQLSTATE '45000' commonly arrives as error 1644.
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
    """Convert an aware datetime to UTC for MariaDB DATETIME columns."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise AppointmentServiceError(
            "Datetime values must include a timezone offset.",
            400,
        )

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_iso(value: datetime | None) -> str | None:
    """Represent a MariaDB UTC DATETIME as an ISO 8601 UTC timestamp."""

    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat()


def _normalise_appointment(row: dict[str, Any]) -> dict[str, Any]:
    """Map database column names to the API's appointment response."""

    return {
        "appointment_id": row.get("appointment_id", row.get("id")),
        "patient_id": row.get("patient_id"),
        "doctor_id": row.get("doctor_id"),
        "start_at": _utc_iso(
            row.get("start_at_utc", row.get("start_at"))
        ),
        "end_at": _utc_iso(
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
                "start_at": _utc_iso(row["start_at_utc"]),
                "end_at": _utc_iso(row["end_at_utc"]),
            }
            for row in rows
            if row.get("start_at_utc") is not None
            and row.get("end_at_utc") is not None
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
            "cancelled_at": _utc_iso(row["cancelled_at_utc"]),
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
                "cancelled_at": _utc_iso(row["cancelled_at_utc"]),
                "created_at": _utc_iso(row["created_at_utc"]),
            }
            for row in rows
        ]

    except AppointmentServiceError:
        raise
    except Exception as exc:
        _handle_database_error(exc)