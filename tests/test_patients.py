from uuid import uuid4

import pytest


@pytest.fixture
def patient_payload():
    unique_id = uuid4().hex[:12]

    return {
        "first_name": "Grace",
        "last_name": "Njeri",
        "email": f"grace.{unique_id}@example.com",
        "phone": "+254712345678",
    }


def test_register_patient_successfully(client, patient_payload):
    response = client.post(
        "/api/v1/patients",
        json=patient_payload,
    )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["message"] == "Patient registered successfully."

    patient = body["data"]

    assert patient["patient_id"] > 0
    assert patient["first_name"] == patient_payload["first_name"]
    assert patient["last_name"] == patient_payload["last_name"]
    assert patient["email"] == patient_payload["email"]
    assert patient["phone"] == patient_payload["phone"]
    assert patient["is_active"] is True


def test_register_patient_rejects_duplicate_email(client, patient_payload):
    first_response = client.post(
        "/api/v1/patients",
        json=patient_payload,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/patients",
        json=patient_payload,
    )

    assert second_response.status_code == 409
    assert "already exists" in second_response.json()["detail"]


def test_register_patient_rejects_invalid_email(client):
    response = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Grace",
            "last_name": "Njeri",
            "email": "invalid-email",
            "phone": "+254712345678",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    ["first_name", "last_name", "email"],
)
def test_register_patient_requires_mandatory_fields(client, field):
    payload = {
        "first_name": "Grace",
        "last_name": "Njeri",
        "email": "grace.required@example.com",
        "phone": None,
    }

    del payload[field]

    response = client.post(
        "/api/v1/patients",
        json=payload,
    )

    assert response.status_code == 422


def test_register_patient_allows_optional_phone(client, patient_payload):
    patient_payload["phone"] = None

    response = client.post(
        "/api/v1/patients",
        json=patient_payload,
    )

    assert response.status_code == 201
    assert response.json()["data"]["phone"] is None
