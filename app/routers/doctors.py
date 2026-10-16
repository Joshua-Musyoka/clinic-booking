from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.services.appointments import (
    AppointmentServiceError,
    get_doctor_availability,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Doctors"],
)


@router.get("/doctors/{doctor_id}/availability")
def retrieve_doctor_availability(
    doctor_id: int,
    appointment_date: date = Query(alias="date"),
):
    """Return available 30-minute slots for a doctor on a given date."""

    if doctor_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="doctor_id must be greater than zero.",
        )

    try:
        availability = get_doctor_availability(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
        )

        return {
            "success": True,
            "message": "Doctor availability retrieved successfully.",
            "data": availability,
        }

    except AppointmentServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc