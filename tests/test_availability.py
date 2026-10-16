def test_availability_requires_valid_date_format(client):
    response = client.get(
        "/api/v1/doctors/1/availability",
        params={"date": "not-a-date"},
    )

    assert response.status_code == 422


def test_availability_rejects_invalid_doctor_id(client):
    response = client.get(
        "/api/v1/doctors/0/availability",
        params={"date": "2026-10-19"},
    )

    assert response.status_code in (400, 422)