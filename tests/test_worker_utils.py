# tests/test_worker_utils.py
import sys
import os
import pytest

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the function we want to test
from scripts.worker import get_session_key

def test_get_session_key_with_ip():
    """Tests that it correctly extracts an IP address."""
    log_line = "Failed password for user root from 192.168.1.101 port 1234"
    assert get_session_key(log_line) == "ip_192.168.1.101"

def test_get_session_key_with_user():
    """Tests that it falls back to extracting a username."""
    log_line = "session opened for user rksha by (uid=0)"
    assert get_session_key(log_line) == "user_rksha"

def test_get_session_key_with_pid():
    """Tests that it falls back to extracting a PID."""
    log_line = "systemd[1234]: Starting user session."
    assert get_session_key(log_line) == "pid_1234"

def test_get_session_key_no_match():
    """Tests that it returns None when no key can be found."""
    log_line = "This is a generic log message with no key."
    assert get_session_key(log_line) is None
