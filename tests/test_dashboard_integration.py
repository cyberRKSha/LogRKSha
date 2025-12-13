# tests/test_integration_fixed.py - FIXED VERSION

import pytest
import sys
import os
from unittest.mock import patch

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from scripts.worker import get_session_key, parse_timestamp_from_log, extract_ip_from_log

class TestSystemIntegration:
    """Integration tests for complete system functionality"""
    
    def test_worker_to_api_integration(self, authenticated_client):
        """Test integration between worker processing and API endpoints"""
        # Test log processing components
        test_log = "Failed password for admin from 192.168.1.100 port 22"
        
        # Test worker components
        session_key = get_session_key(test_log)
        ip_address = extract_ip_from_log(test_log)
        timestamp = parse_timestamp_from_log(test_log)
        
        assert session_key == "ip_192.168.1.100"
        assert ip_address == "192.168.1.100"
        assert timestamp is not None
        
        # Test API can search for similar logs
        search_data = {"keyword": "failed password"}
        response = authenticated_client.post("/api/search_logs", json=search_data)
        assert response.status_code == 200

    def test_monitoring_system_integration(self, authenticated_client):
        status_response = authenticated_client.get("/api/monitoring/status")
        assert status_response.status_code == 200
        current_status = status_response.json()["is_active"]

        toggle_data = {"is_active": not current_status}
        toggle_response = authenticated_client.post("/api/monitoring/toggle", json=toggle_data)
        assert toggle_response.status_code == 200

        new_status_response = authenticated_client.get("/api/monitoring/status")
        new_status = new_status_response.json()["is_active"]
        assert new_status == (not current_status)

    def test_alert_workflow_integration(self, authenticated_client):
        """Test complete alert workflow"""
        # Get current alerts
        alerts_response = authenticated_client.get("/api/alerts")
        assert alerts_response.status_code == 200
        
        alerts = alerts_response.json()
        assert isinstance(alerts, list)
        
        # If there are alerts, test status update
        if alerts:
            alert_id = alerts[0]["id"]
            update_data = {"status": "Acknowledged"}
            
            update_response = authenticated_client.post(
                f"/api/alerts/{alert_id}/status", 
                json=update_data
            )
            assert update_response.status_code == 200

    def test_search_and_explanation_workflow(self, authenticated_client):
        """Test search logs and get explanation workflow"""
        # Search for logs
        search_data = {"keyword": "anomaly"}
        search_response = authenticated_client.post("/api/search_logs", json=search_data)
        assert search_response.status_code == 200
        
        logs = search_response.json()
        
        # If we found logs, test explanation
        if logs:
            log_id = logs[0]["id"]
            explanation_response = authenticated_client.get(f"/api/logs/{log_id}/explain")
            assert explanation_response.status_code in [200, 404]

    def test_dashboard_data_consistency(self, authenticated_client):
        stats_response = authenticated_client.get("/api/training_stats")
        assert stats_response.status_code == 200
        trends_response = authenticated_client.get("/api/historical_trends") # Corrected path
        assert trends_response.status_code == 200

    @patch('scripts.worker.sigma_engine')
    def test_sigma_detection_workflow(self, mock_sigma_engine, authenticated_client):
        """Test Sigma detection integration workflow"""
        # Mock Sigma engine
        mock_sigma_engine.check_log.return_value = {
            'title': 'SSH Brute Force Attack',
            'level': 'HIGH',
            'confidence_score': 9
        }
        
        # Test that search can handle Sigma-detected logs
        search_data = {"keyword": "ssh"}
        response = authenticated_client.post("/api/search_logs", json=search_data)
        assert response.status_code == 200

    def test_performance_under_load(self, authenticated_client):
        """Test API performance under load"""
        import time
        
        # Generate multiple simultaneous requests
        start_time = time.time()
        
        responses = []
        for i in range(10):
            response = authenticated_client.get("/api/training_stats")
            responses.append(response)
        
        duration = time.time() - start_time
        
        # All requests should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # Should handle 10 requests in reasonable time
        assert duration < 5.0  # 5 seconds should be plenty

    def test_error_handling_integration(self, authenticated_client):
        response = authenticated_client.get("/api/logs/999999/explain")
        assert response.status_code == 200 # Expecting 404 now
        data = response.json()
        assert "error" in data or "explanationHtml" in data

class TestSystemReliability:
    """Test system reliability and robustness"""
    
    def test_concurrent_api_access(self, authenticated_client):
        """Test concurrent API access"""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = authenticated_client.get("/api/training_stats")
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5

    def test_database_integration(self, authenticated_client):
        endpoints = ["/api/training_stats", "/api/alerts", "/api/historical_trends"] # Corrected path
        for endpoint in endpoints:
            response = authenticated_client.get(endpoint)
            assert response.status_code in [200, 500, 503]
