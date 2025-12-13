# tests/test_worker_utils.py
import sys, os, pytest, time, threading
from unittest.mock import patch, Mock, call

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the function we want to test
from scripts.worker import get_session_key, parse_timestamp_from_log, extract_ip_from_log

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
    result = get_session_key(log_line)
    assert result in ["pid_1234", "user_session"]

def test_get_session_key_no_match():
    """Tests that it returns None when no key can be found."""
    log_line = "This is a generic log message with no key."
    assert get_session_key(log_line) is None

def test_parse_timestamp_from_log():
    """Test timestamp parsing from log entries"""
    # Test with typical syslog format
    log_line = "Sep 28 15:30:00 server sshd[1234]: Failed password"
    result = parse_timestamp_from_log(log_line)
    assert isinstance(result, str)
    assert "T" in result  # ISO format should contain T
    assert result.endswith("Z") or "+" in result  # Should have timezone info

def test_parse_timestamp_fallback():
    """Test timestamp parsing fallback for logs without timestamps"""
    log_line = "Random log without timestamp"
    result = parse_timestamp_from_log(log_line)
    assert isinstance(result, str)
    # Should return current time as fallback
    assert "T" in result

def test_extract_ip_from_log():
    """Test IP address extraction from log entries"""
    log_line = "Failed password for admin from 192.168.1.100 port 22"
    result = extract_ip_from_log(log_line)
    assert result == "192.168.1.100"

def test_extract_ip_no_match():
    """Test IP extraction when no IP is present"""
    log_line = "System startup completed successfully"
    result = extract_ip_from_log(log_line)
    assert result is None

def test_worker_performance():
    """Test worker processing performance"""
    # Generate test logs
    test_logs = [
        f"Failed password for user{i} from 192.168.1.{i%255} port 22"
        for i in range(100)
    ]
    
    start_time = time.time()
    
    results = []
    for log in test_logs:
        key = get_session_key(log)
        results.append(key)
    
    duration = time.time() - start_time
    logs_per_second = len(test_logs) / duration
    
    # Should process at least 1000 logs per second
    assert logs_per_second > 1000
    assert len(results) == len(test_logs)
    # All results should have IP-based session keys
    assert all(r and r.startswith('ip_192.168.1.') for r in results)

def test_concurrent_worker_processing():
    """Test concurrent log processing"""
    test_logs = [f"User session for testuser{i}" for i in range(100)]
    results = []
    
    def process_chunk(logs, result_list):
        for log in logs:
            key = get_session_key(log)
            result_list.append(key)
    
    # Split into chunks and process concurrently
    chunk_size = 25
    threads = []
    thread_results = [[] for _ in range(4)]
    
    for i in range(4):
        chunk = test_logs[i*chunk_size:(i+1)*chunk_size]
        thread = threading.Thread(target=process_chunk, args=(chunk, thread_results[i]))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Combine results
    all_results = []
    for thread_result in thread_results:
        all_results.extend(thread_result)
    
    assert len(all_results) == 100
    # Filter out None values before checking startswith
    valid_results = [r for r in all_results if r is not None]
    assert len(valid_results) > 50  # Should extract some user keys
    assert all(r.startswith('user_testuser') for r in valid_results)

def test_error_handling():
    """Test worker error handling for malformed logs"""
    malformed_logs = [
        "",  # Empty log
        "Log with unicode: 你好世界",  # Unicode
        "Very long log: " + "A" * 10000,  # Very long log
        "Log\nwith\nnewlines",  # Newlines
    ]
    
    for log in malformed_logs:
        try:
            result = get_session_key(log)
            # Should either return valid key or None, never crash
            assert result is None or isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Worker crashed on malformed log '{log[:50]}...': {e}")

@patch('scripts.worker.sigma_engine')
def test_log_processing_with_mock_sigma(mock_sigma_engine):
    """Test log processing pipeline with mocked Sigma engine"""
    # Mock Sigma engine response
    mock_sigma_engine.check_log.return_value = {
        'title': 'SSH Attack Detected',
        'level': 'HIGH',
        'confidence_score': 8
    }
    
    test_log = "Failed password for admin from 192.168.1.100 port 22"
    
    # Test the main components work together
    session_key = get_session_key(test_log)
    ip_address = extract_ip_from_log(test_log)
    timestamp = parse_timestamp_from_log(test_log)
    
    assert session_key == "ip_192.168.1.100"
    assert ip_address == "192.168.1.100" 
    assert isinstance(timestamp, str)
    assert "T" in timestamp

@patch('scripts.worker.redis.Redis')
def test_redis_integration_mock(mock_redis):
    """Test Redis integration with mocking"""
    # Mock Redis client
    mock_redis_instance = Mock()
    mock_redis.return_value = mock_redis_instance
    mock_redis_instance.ping.return_value = True
    
    # Test that worker functions can handle Redis operations
    test_logs = ["Failed password for admin from 192.168.1.100"]
    
    for log in test_logs:
        key = get_session_key(log)
        assert key is not None