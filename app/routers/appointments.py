from fastapi import APIRouter, HTTPException, Path, Query, status

from app.schemas.appointments import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentReschedule,
)
from app.services.appointments import (
    AppointmentServiceError,
    book_appointment,
    cancel_appointment,
    get_appointment,
    get_patient_appointments,
    reschedule_appointment,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Appointments"],
)


def handle_service_error(exc: AppointmentServiceError) -> None:
    """Convert service errors into HTTP responses."""
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.message,
    ) from exc


@router.post(
    "/appointments",
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(payload: AppointmentCreate):
    """Book a new appointment."""

    try:
        appointment = book_appointment(
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            start_at=payload.start_at,
        )

        return {
            "success": True,
            "message": "Appointment booked successfully.",
            "data": appointment,
        }

    except AppointmentServiceError as exc:
        handle_service_error(exc)


@router.post("/appointments/{appointment_id}/cancel")
def cancel_existing_appointment(
    appointment_id: int = Path(gt=0),
    payload: AppointmentCancel = ...,
):
    """Cancel an existing appointment."""

    try:
        appointment = cancel_appointment(
            appointment_id=appointment_id,
            reason=payload.reason,
        )

        return {
            "success": True,
            "message": "Appointment cancelled successfully.",
            "data": appointment,
        }

    except AppointmentServiceError as exc:
        handle_service_error(exc)


@router.patch("/appointments/{appointment_id}")
def reschedule_existing_appointment(
    appointment_id: int = Path(gt=0),
    payload: AppointmentReschedule = ...,
):
    """Reschedule an existing appointment."""

    try:
        appointment = reschedule_appointment(
            appointment_id=appointment_id,
            new_start_at=payload.start_at,
        )

        return {
            "success": True,
            "message": "Appointment rescheduled successfully.",
            "data": appointment,
        }

    except AppointmentServiceError as exc:
        handle_service_error(exc)


@router.get("/appointments/{appointment_id}")
def retrieve_appointment(
    appointment_id: int = Path(gt=0),
):
    """Retrieve an appointment by ID."""

    try:
        appointment = get_appointment(appointment_id)

        return {
            "success": True,
            "message": "Appointment retrieved successfully.",
            "data": appointment,
        }

    except AppointmentServiceError as exc:
        handle_service_error(exc)


@router.get("/patients/{patient_id}/appointments")
def retrieve_patient_appointments(
    patient_id: int = Path(gt=0),
    upcoming_only: bool = Query(default=False),
):
    """Retrieve a patient's appointments."""

    try:
        appointments = get_patient_appointments(
            patient_id=patient_id,
            upcoming_only=upcoming_only,
        )

        return {
            "success": True,
            "message": "Patient appointments retrieved successfully.",
            "data": appointments,
        }

    except AppointmentServiceError as exc:
        handle_service_error(exc)