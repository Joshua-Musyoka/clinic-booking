def test_booking_accepts_swagger_nairobi_local_time_example(client):
    response = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": 1,
            "doctor_id": 1,
            "start_at": "2026-10-23T10:00:00+03:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["start_at"] == "2026-10-23T07:00:00+00:00"


def test_swagger_appointment_examples_use_nairobi_local_time(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    example = ["2026-10-23T10:00:00+03:00"]
    assert schemas["AppointmentCreate"]["properties"]["start_at"]["examples"] == example
    assert schemas["AppointmentReschedule"]["properties"]["start_at"]["examples"] == example


def test_booking_rejects_invalid_patient_id(client):
    response = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": 0,
            "doctor_id": 1,
            "start_at": "2026-10-19T10:00:00+03:00",
        },
    )

    assert response.status_code == 422
