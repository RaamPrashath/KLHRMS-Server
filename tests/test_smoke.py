"""
Smoke tests — verify the app boots and core routes respond.
No DB or Redis required.
"""


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "KL HRMS API"


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "checks" in body


def test_protected_endpoint_requires_auth(client):
    """Employees endpoint must reject unauthenticated requests."""
    resp = client.get("/api/v1/employees")
    assert resp.status_code == 401
