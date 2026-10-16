from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.patients import PatientCreate
from app.schemas.patient_updates import PatientUpdate

from app.services.patients import (
    PatientServiceError,
    activate_patient,
    create_patient,
    deactivate_patient,
    get_patient,
    list_patients,
    update_patient,
)

router = APIRouter(
    prefix="/api/v1/patients",
    tags=["Patients"],
)


@router.get("")
def retrieve_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    active_only: bool = Query(default=True),
):
    try:
        result = list_patients(
            page=page,
            page_size=page_size,
            search=search,
            active_only=active_only,
        )

        return {
            "success": True,
            "message": "Patients retrieved successfully.",
            "data": result["data"],
            "pagination": result["pagination"],
        }

    except PatientServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def register_patient(patient: PatientCreate):
    try:
        created_patient = create_patient(
            first_name=patient.first_name,
            last_name=patient.last_name,
            email=str(patient.email),
            phone=patient.phone,
        )

        return {
            "success": True,
            "message": "Patient registered successfully.",
            "data": created_patient,
        }

    except PatientServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc        



@router.patch("/{patient_id}/deactivate")
def deactivate_patient_endpoint(patient_id: int):
    try:
        patient = deactivate_patient(patient_id)

        return {
            "success": True,
            "message": "Patient deactivated successfully.",
            "data": patient,
        }

    except PatientServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc


@router.patch("/{patient_id}/activate")
def activate_patient_endpoint(patient_id: int):
    try:
        patient = activate_patient(patient_id)

        return {
            "success": True,
            "message": "Patient activated successfully.",
            "data": patient,
        }

    except PatientServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc        


@router.get("/{patient_id}")
def retrieve_patient(patient_id: int):
    try:
        patient = get_patient(patient_id)

        return {
            "success": True,
            "message": "Patient retrieved successfully.",
            "data": patient,
        }

    except PatientServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc        


@router.patch("/{patient_id}")
def modify_patient(patient_id: int, patient: PatientUpdate):
    try:
        changes = patient.model_dump(exclude_unset=True)

        updated_patient = update_patient(
            patient_id=patient_id,
            changes=changes,
        )

        return {
            "success": True,
            "message": "Patient updated successfully.",
            "data": updated_patient,
        }

    except PatientServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc        


        