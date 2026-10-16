def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True


def test_list_patients_endpoint(client):
    response = client.get(
        "/api/v1/patients",
        params={"page": 1, "page_size": 5},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert "data" in body
    assert "pagination" in body

    pagination = body["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 5


def test_list_patients_rejects_invalid_page(client):
    response = client.get(
        "/api/v1/patients",
        params={"page": 0},
    )

    assert response.status_code == 422


def test_list_patients_rejects_invalid_page_size(client):
    response = client.get(
        "/api/v1/patients",
        params={"page_size": 101},
    )

    assert response.status_code == 422