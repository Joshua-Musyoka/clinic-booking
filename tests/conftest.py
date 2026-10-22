import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client(monkeypatch):
    from app.routers import appointments
    from app.routers import patients

    patient_records = {}
    next_patient_id = 1

    def list_patients(page=1, page_size=20, search=None, active_only=True):
        matching_patients = list(patient_records.values())
        start = (page - 1) * page_size
        page_patients = matching_patients[start : start + page_size]
        total = len(matching_patients)
        return {
            "data": page_patients,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    def create_patient(first_name, last_name, email, phone=None):
        nonlocal next_patient_id

        email = email.strip().lower()
        if any(record["email"] == email for record in patient_records.values()):
            from app.services.patients import PatientServiceError

            raise PatientServiceError(
                "A patient with this email address already exists.", 409
            )

        patient = {
            "patient_id": next_patient_id,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "email": email,
            "phone": phone.strip() if phone else None,
            "is_active": True,
        }
        patient_records[next_patient_id] = patient
        next_patient_id += 1
        return patient

    monkeypatch.setattr(patients, "list_patients", list_patients)
    monkeypatch.setattr(patients, "create_patient", create_patient)
    monkeypatch.setattr(
        appointments,
        "book_appointment",
        lambda patient_id, doctor_id, start_at: {
            "appointment_id": 1,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_at": start_at.isoformat(),
            "end_at": start_at.isoformat(),
            "status": "scheduled",
        },
    )

    with TestClient(app) as test_client:
        yield test_client
