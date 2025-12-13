# tests/conftest.py
import pytest, numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app import auth_utils
from pathlib import Path
from unittest.mock import Mock, patch

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

@pytest.fixture(autouse=True)
def mock_sentence_transformer(monkeypatch):
    """
    Mocks the SentenceTransformer to prevent downloading and loading the large model
    during tests. It returns a correctly-shaped dummy vector.
    """
    class MockSentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass
        def encode(self, sentences, **kwargs):
            # The real model produces a 384-dimensional vector. We'll mimic that.
            # If sentences is a list of strings, return a list of vectors.
            if isinstance(sentences, list):
                return np.zeros((len(sentences), 384), dtype=np.float32)
            # If it's a single string, return a single vector.
            return np.zeros(384, dtype=np.float32)

    # Tell pytest to replace the real SentenceTransformer with our fake one
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", MockSentenceTransformer)

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

@pytest.fixture(autouse=True)
def mock_sigma_engine(monkeypatch):
    """Mock Sigma engine to prevent rule loading during tests"""
    class MockSigmaEngine:
        def __init__(self):
            self.rules = [
                {
                    'title': 'Test SSH Brute Force',
                    'level': 'HIGH',
                    'detection': {'keywords': ['failed password', 'ssh']},
                    'tags': ['attack.credential_access']
                },
                {
                    'title': 'Test Privilege Escalation', 
                    'level': 'CRITICAL',
                    'detection': {'keywords': ['sudo', 'root']},
                    'tags': ['attack.privilege_escalation']
                }
            ]
        
        def check_log(self, log_entry):
            # Simple mock detection logic
            log_lower = log_entry.lower()
            for rule in self.rules:
                for keyword in rule['detection']['keywords']:
                    if keyword in log_lower:
                        return {
                            'title': rule['title'],
                            'level': rule['level'], 
                            'confidence_score': 8,
                            'matched_keywords': [keyword],
                            'rule_id': 'test-001'
                        }
            return None
    
    monkeypatch.setattr("scripts.sigma_engine.SigmaEngine", MockSigmaEngine)

@pytest.fixture
def mock_worker_components(monkeypatch):
    """Mock external dependencies for worker testing"""
    # Mock file operations
    mock_file = Mock()
    mock_file.write = Mock()
    mock_file.flush = Mock()
    
    # Mock database operations
    mock_db = Mock()
    mock_db.execute = Mock()
    mock_db.commit = Mock()
    
    return {'file': mock_file, 'db': mock_db}

@pytest.fixture
def sample_log_entries():
    """Sample log entries for testing across different modules"""
    return {
        'ssh_brute_force': [
            "Sep 28 15:30:00 server sshd[1234]: Failed password for admin from 192.168.1.100 port 22 ssh2",
            "Sep 28 15:30:01 server sshd[1235]: Failed password for root from 192.168.1.100 port 22 ssh2",
            "Sep 28 15:30:02 server sshd[1236]: Invalid user hacker from 192.168.1.100 port 22"
        ],
        'privilege_escalation': [
            "Sep 28 15:31:00 server sudo: testuser : TTY=pts/0 ; PWD=/home/testuser ; USER=root ; COMMAND=/bin/bash",
            "Sep 28 15:31:01 server sudo: testuser : USER=root ; COMMAND=/usr/bin/cat /etc/shadow"
        ],
        'web_attacks': [
            "Sep 28 15:32:00 server nginx[5678]: GET /../../../etc/passwd HTTP/1.1 404",
            "Sep 28 15:32:01 server nginx[5679]: POST /uploads/shell.php HTTP/1.1 200"
        ],
        'normal_logs': [
            "Sep 28 15:33:00 server systemd[1]: Started user session",
            "Sep 28 15:33:01 server cron[1234]: Job completed successfully"
        ]
    }

@pytest.fixture
def mock_attack_simulator(monkeypatch):
    """Mock attack simulator functions"""
    def mock_generate_ssh_logs(ip, count=5):
        return [f"Failed password for user{i} from {ip}" for i in range(count)]
    
    def mock_generate_privilege_logs(user, count=3):
        return [f"sudo: {user} : USER=root ; COMMAND=/bin/bash" for _ in range(count)]
    
    monkeypatch.setattr("scripts.att_sim.generate_ssh_brute_force_logs", mock_generate_ssh_logs)
    monkeypatch.setattr("scripts.att_sim.generate_privilege_escalation_logs", mock_generate_privilege_logs)