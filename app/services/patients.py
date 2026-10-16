from datetime import datetime
from typing import Any

import pymysql

from app.database import database_connection


class PatientServiceError(Exception):
    """Raised when a patient listing operation fails."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def list_patients(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    Retrieve a paginated list of patients using sp_list_patients.

    The stored procedure returns:
      1. Patient records.
      2. Total number of matching patients.
    """
    if page < 1:
        raise PatientServiceError("Page must be at least 1.", 400)

    if not 1 <= page_size <= 100:
        raise PatientServiceError(
            "Page size must be between 1 and 100.", 400
        )

    search_term = search.strip() if search and search.strip() else None

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CALL sp_list_patients(%s, %s, %s, %s)",
                    (page, page_size, search_term, active_only),
                )

                # Result set 1: patient records
                patients = list(cursor.fetchall())

                # Result set 2: total matching records
                total = 0

                if cursor.nextset():
                    count_row = cursor.fetchone()
                    if count_row:
                        total = int(count_row["total"])

                # Drain any remaining result sets from CALL.
                while cursor.nextset():
                    if cursor.description is not None:
                        cursor.fetchall()

        total_pages = (total + page_size - 1) // page_size

        return {
            "data": patients,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        }

    except PatientServiceError:
        raise

    except pymysql.MySQLError as exc:
        error_message = str(exc)

        if "INVALID_PAGE_SIZE" in error_message:
            raise PatientServiceError(
                "Page size must be between 1 and 100.", 400
            ) from exc

        if "INVALID_PAGE" in error_message:
            raise PatientServiceError(
                "Page must be at least 1.", 400
            ) from exc

        raise PatientServiceError(
            "Unable to retrieve patients from the database.", 500
        ) from exc


def create_patient(
    first_name: str,
    last_name: str,
    email: str,
    phone: str | None = None,
) -> dict[str, Any]:
    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()
    phone = phone.strip() if phone else None

    if not first_name or not last_name or not email:
        raise PatientServiceError(
            "First name, last name, and email are required.",
            400,
        )

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CALL sp_create_patient(%s, %s, %s, %s)",
                    (first_name, last_name, email, phone),
                )

                patient = cursor.fetchone()

                while cursor.nextset():
                    if cursor.description is not None:
                        cursor.fetchall()

                if not patient:
                    raise PatientServiceError(
                        "Patient registration did not return a record.",
                        500,
                    )

            connection.commit()

        for field in ("created_at", "updated_at"):
            value = patient.get(field)

            if isinstance(value, datetime):
                patient[field] = value.isoformat()

        patient["is_active"] = bool(patient["is_active"])

        return patient

    except PatientServiceError:
        raise

    except pymysql.err.IntegrityError as exc:
        if exc.args and exc.args[0] == 1062:
            raise PatientServiceError(
                "A patient with this email address already exists.",
                409,
            ) from exc

        raise PatientServiceError(
            "Unable to register the patient.",
            500,
        ) from exc

    except pymysql.MySQLError as exc:
        error_message = str(exc)

        if "PATIENT_EMAIL_EXISTS" in error_message:
            raise PatientServiceError(
                "A patient with this email address already exists.",
                409,
            ) from exc

        if "INVALID_FIRST_NAME" in error_message:
            raise PatientServiceError("First name is required.", 400) from exc

        if "INVALID_LAST_NAME" in error_message:
            raise PatientServiceError("Last name is required.", 400) from exc

        if "INVALID_EMAIL" in error_message:
            raise PatientServiceError("Email is required.", 400) from exc

        raise PatientServiceError(
            "Unable to register the patient.",
            500,
        ) from exc

def get_patient(patient_id: int) -> dict[str, Any]:
    if patient_id <= 0:
        raise PatientServiceError(
            "Patient ID must be greater than zero.",
            400,
        )

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id AS patient_id,
                        first_name,
                        last_name,
                        email,
                        phone,
                        is_active,
                        created_at,
                        updated_at
                    FROM patients
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (patient_id,),
                )

                patient = cursor.fetchone()

        if not patient:
            raise PatientServiceError(
                "Patient not found.",
                404,
            )

        for field in ("created_at", "updated_at"):
            value = patient.get(field)

            if value is not None:
                patient[field] = value.isoformat()

        patient["is_active"] = bool(patient["is_active"])

        return patient

    except PatientServiceError:
        raise

    except pymysql.MySQLError as exc:
        raise PatientServiceError(
            "Unable to retrieve patient from the database.",
            500,
        ) from exc        


def update_patient(
    patient_id: int,
    changes: dict[str, Any],
) -> dict[str, Any]:
    from datetime import datetime

    if patient_id <= 0:
        raise PatientServiceError("Patient ID must be greater than zero.", 400)

    if not changes:
        raise PatientServiceError("Provide at least one field to update.", 400)

    allowed_fields = {"first_name", "last_name", "email", "phone"}

    if not set(changes).issubset(allowed_fields):
        raise PatientServiceError("Invalid patient fields supplied.", 400)

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CALL sp_update_patient(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        patient_id,
                        "first_name" in changes,
                        changes.get("first_name"),
                        "last_name" in changes,
                        changes.get("last_name"),
                        "email" in changes,
                        str(changes["email"]) if changes.get("email") is not None else None,
                        "phone" in changes,
                        changes.get("phone"),
                    ),
                )

                patient = cursor.fetchone()

                while cursor.nextset():
                    if cursor.description is not None:
                        cursor.fetchall()

            connection.commit()

        if not patient:
            raise PatientServiceError("Patient not found.", 404)

        for field in ("created_at", "updated_at"):
            value = patient.get(field)
            if isinstance(value, datetime):
                patient[field] = value.isoformat()

        patient["is_active"] = bool(patient["is_active"])

        return patient

    except PatientServiceError:
        raise

    except pymysql.err.IntegrityError as exc:
        if exc.args and exc.args[0] == 1062:
            raise PatientServiceError(
                "A patient with this email address already exists.",
                409,
            ) from exc

        raise PatientServiceError("Unable to update patient.", 500) from exc

    except pymysql.MySQLError as exc:
        error_message = str(exc)

        if "PATIENT_NOT_FOUND" in error_message:
            raise PatientServiceError("Patient not found.", 404) from exc

        if "PATIENT_EMAIL_EXISTS" in error_message:
            raise PatientServiceError(
                "A patient with this email address already exists.",
                409,
            ) from exc

        if "INVALID_PATIENT_ID" in error_message:
            raise PatientServiceError(
                "Patient ID must be greater than zero.",
                400,
            ) from exc

        if "INVALID_FIRST_NAME" in error_message:
            raise PatientServiceError("First name cannot be empty.", 400) from exc

        if "INVALID_LAST_NAME" in error_message:
            raise PatientServiceError("Last name cannot be empty.", 400) from exc

        if "INVALID_EMAIL" in error_message:
            raise PatientServiceError("Email cannot be empty.", 400) from exc

        raise PatientServiceError("Unable to update patient.", 500) from exc        


def _change_patient_status(
    patient_id: int,
    procedure_name: str,
    active: bool,
) -> dict[str, Any]:
    from datetime import datetime

    if patient_id <= 0:
        raise PatientServiceError(
            "Patient ID must be greater than zero.",
            400,
        )

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CALL {procedure_name}(%s)",
                    (patient_id,),
                )

                patient = cursor.fetchone()

                while cursor.nextset():
                    if cursor.description is not None:
                        cursor.fetchall()

            connection.commit()

        if not patient:
            raise PatientServiceError("Patient not found.", 404)

        for field in ("created_at", "updated_at"):
            value = patient.get(field)

            if isinstance(value, datetime):
                patient[field] = value.isoformat()

        patient["is_active"] = bool(patient["is_active"])

        return patient

    except PatientServiceError:
        raise

    except pymysql.MySQLError as exc:
        error_message = str(exc)

        if "PATIENT_NOT_FOUND" in error_message:
            raise PatientServiceError(
                "Patient not found.",
                404,
            ) from exc

        if "INVALID_PATIENT_ID" in error_message:
            raise PatientServiceError(
                "Patient ID must be greater than zero.",
                400,
            ) from exc

        raise PatientServiceError(
            "Unable to update patient status.",
            500,
        ) from exc


def deactivate_patient(patient_id: int) -> dict[str, Any]:
    return _change_patient_status(
        patient_id=patient_id,
        procedure_name="sp_deactivate_patient",
        active=False,
    )


def activate_patient(patient_id: int) -> dict[str, Any]:
    return _change_patient_status(
        patient_id=patient_id,
        procedure_name="sp_activate_patient",
        active=True,
    )        