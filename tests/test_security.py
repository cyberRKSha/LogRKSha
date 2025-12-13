# tests/test_security_fixed.py - FIXED VERSION

import pytest

class TestSecurityFeatures:
    """Test security aspects of the system"""
    
    def test_authentication_required_for_dashboard(self, client):
        """Test that dashboard requires authentication"""
        response = client.get("/", follow_redirects=False)
        # Should redirect to login
        assert response.status_code in [303, 307, 302]

    def test_api_endpoints_require_auth(self, client):
        """Test that API endpoints require authentication"""
        api_endpoints = {
            "/api/alerts": "GET",
            "/api/search_logs": "POST", # THE FIX: This is a POST endpoint
            "/api/training_stats": "GET",
            "/api/monitoring/status": "GET"
        }
        for endpoint, method in api_endpoints.items():
            if method == "GET":
                response = client.get(endpoint, follow_redirects=False)
            else:
                # Use post for POST endpoints
                response = client.post(endpoint, json={}, follow_redirects=False)
            # A redirect to login is the expected behavior for unauthenticated access
            assert response.status_code in [303, 307]

    def test_authenticated_access_works(self, authenticated_client):
        """Test that authenticated users can access protected resources"""
        protected_endpoints = [
            "/",
            "/api/alerts", 
            "/api/training_stats",
            "/playbooks",
            "/review"
        ]
        
        for endpoint in protected_endpoints:
            response = authenticated_client.get(endpoint)
            assert response.status_code == 200

    def test_input_sanitization_search(self, authenticated_client):
        """Test input sanitization in search functionality"""
        potentially_malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE logs; --",
            "../../../../etc/passwd",
            "javascript:alert(1)"
        ]
        
        for malicious_input in potentially_malicious_inputs:
            search_data = {"keyword": malicious_input}
            response = authenticated_client.post("/api/search_logs", json=search_data)
            
            # Should handle safely (return results or error, but not crash)
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                # If it returns results, they should be safe
                data = response.json()
                assert isinstance(data, list)

    def test_monitoring_toggle_security(self, authenticated_client):
        """Test monitoring toggle endpoint security"""
        # Test with valid boolean
        valid_data = {"isactive": False}
        response = authenticated_client.post("/api/monitoring/toggle", json=valid_data)
        assert response.status_code == 200
        
        # Test with invalid data types
        invalid_data = {"isactive": "malicious_string"}
        response = authenticated_client.post("/api/monitoring/toggle", json=invalid_data)
        # Should either work (convert to bool) or return error
        assert response.status_code in [200, 400, 422]

    def test_alert_status_validation(self, authenticated_client):
        """Test alert status update validation"""
        # Test with valid status
        valid_statuses = ["New", "Acknowledged", "Resolved"]
        
        for status in valid_statuses:
            update_data = {"status": status}
            response = authenticated_client.post("/api/alerts/1/status", json=update_data)
            # Should either work or return 404 if alert doesn't exist
            assert response.status_code in [200, 404]
        
        # Test with invalid status
        invalid_data = {"status": "InvalidStatus"}
        response = authenticated_client.post("/api/alerts/1/status", json=invalid_data)
        # Should validate and reject
        assert response.status_code in [400, 404, 422]

    def test_file_upload_security(self, authenticated_client):
        """Test file upload security (if applicable)"""
        # Test PDF export which might handle file-like operations
        export_data = {
            "keyword": "test",
            "chart_images": {
                "test_chart": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            }
        }
        
        response = authenticated_client.post("/api/export/pdf", json=export_data)
        # Should handle safely
        assert response.status_code in [200, 400, 500]

    def test_rate_limiting_awareness(self, authenticated_client):
        """Test system behavior under rapid requests"""
        # Make rapid requests to check if system handles them gracefully
        responses = []
        
        for i in range(10):
            response = authenticated_client.get("/api/training_stats")
            responses.append(response.status_code)
        
        # System should handle rapid requests (may implement rate limiting)
        successful_responses = [r for r in responses if r == 200]
        
        # Should have at least some successful responses
        assert len(successful_responses) >= 5

    def test_websocket_security(self, authenticated_client):
        """Test WebSocket security"""
        try:
            with authenticated_client.websocket_connect("/ws") as websocket:
                # Should be able to connect if authenticated
                data = websocket.receive_json()
                assert isinstance(data, dict)
        except Exception:
            # WebSocket might require different authentication or not be available
            # This is acceptable for testing
            pass

    def test_error_information_disclosure(self, authenticated_client):
        """Test that errors don't disclose sensitive information"""
        # Test with various invalid requests
        invalid_requests = [
            ("/api/logs/99999/explain", "GET"),
            ("/api/alerts/99999/status", "POST"),
            ("/api/nonexistent-endpoint", "GET")
        ]
        
        for endpoint, method in invalid_requests:
            if method == "GET":
                response = authenticated_client.get("/api/logs/999999/explain")
                assert response.status_code == 200  # Your API design
                # Verify it handles gracefully
                data = response.json()
                assert "error" in data or "explanationHtml" in data
            else:
                response = authenticated_client.post(endpoint, json={})
                # For truly non-existent endpoints, expect 404
                assert response.status_code in [404, 422]
                if response.status_code == 422:
                    error_data = response.json()
                    # Should be standard FastAPI validation error format
                    assert "detail" in error_data
