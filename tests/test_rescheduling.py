def test_booking_rejects_missing_timezone(client):
    response = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": 1,
            "doctor_id": 1,
            "start_at": "2026-10-19T10:00:00",
        },
    )

    assert response.status_code == 422


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