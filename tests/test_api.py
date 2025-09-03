# tests/test_api.py
from app.api.models import SearchQuery

def test_read_main_dashboard_authenticated(authenticated_client):
    """Tests if an authenticated user can successfully load the dashboard."""
    response = authenticated_client.get("/")
    assert response.status_code == 200
    assert "<title>Log Anomaly Dashboard</title>" in response.text

def test_read_main_dashboard_redirects_when_unauthenticated(client):
    """Tests if an unauthenticated user gets redirected to the login page."""
    response = client.get("/", follow_redirects=False)
    # THE FIX: Assert the correct 303 status code
    assert response.status_code == 303

def test_get_training_stats_authenticated(authenticated_client):
    """Tests the /api/training_stats endpoint for an authenticated user."""
    response = authenticated_client.get("/api/training_stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data

def test_search_logs_unauthenticated(client):
    """ Tests that search requires authentication. """
    response = client.post("/api/search_logs", json={"keyword": "test"}, follow_redirects=False)
    assert response.status_code in [303, 307] # Should redirect to login

def test_get_alerts_requires_auth(client):
    """Tests that unauthenticated users cannot access the alerts endpoint."""
    response = client.get("/api/alerts", follow_redirects=False)
    # Expect a 401 Unauthorized or a redirect to login, depending on your setup.
    # A redirect (307/303) is also a valid way of handling this.
    assert response.status_code in [401, 307, 303]

def test_get_alerts_returns_list(authenticated_client):
    """Tests that the alerts endpoint returns a list for authenticated users."""
    response = authenticated_client.get("/api/alerts")
    assert response.status_code == 200
    # The response should be a list (it can be empty, but it must be a list)
    assert isinstance(response.json(), list)