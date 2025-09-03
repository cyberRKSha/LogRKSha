# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import auth_utils

@pytest.fixture(autouse=True)
def mock_geoip_reader(monkeypatch):

    class MockReader:
        def __init__(self, *args, **kwargs):
            pass  # Ignore the path argument

        def city(self, ip_address):
            # A fake city object
            class MockCity:
                def __init__(self):
                    self.city = type("City", (), {"name": "Test City"})()
                    self.country = type("Country", (), {"name": "Testland"})()
                    self.location = type("Location", (), {"latitude": 0, "longitude": 0})()
            return MockCity()

        def close(self):
            pass

    # Tell pytest to replace the real Reader with our fake one
    monkeypatch.setattr("geoip2.database.Reader", MockReader)


@pytest.fixture(scope="function")
def client():
    """ A fixture that creates a new, unauthenticated TestClient for each test. """
    # Clear any dependency overrides from previous tests before creating the client
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    # Clean up after the test is done
    app.dependency_overrides = {}

@pytest.fixture(scope="function")
def authenticated_client():
    """ A fixture that creates a TestClient that is "logged in" as a test user. """
    def override_get_current_user():
        return {"username": "testuser", "id": 1}
    
    # Clear any old overrides and apply the new one
    app.dependency_overrides = {}
    app.dependency_overrides[auth_utils.get_current_user] = override_get_current_user
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up after the test is done
    app.dependency_overrides = {}