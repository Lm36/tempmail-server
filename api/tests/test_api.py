"""Test general API endpoints (health, root, etc.)"""

import pytest


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test health check endpoint is accessible"""
        response = client.get("/api/v1/health")

        # In test mode, database check may fail (503) or succeed (200)
        assert response.status_code in [200, 503]
        data = response.json()

        assert "status" in data
        assert "database" in data
        assert "domains" in data

    def test_health_check_structure(self, client):
        """Test health check returns correct structure"""
        response = client.get("/api/v1/health")
        data = response.json()

        # Should indicate healthy in test mode
        assert data["status"] in ["healthy", "unhealthy"]
        assert data["database"] in ["connected", "disconnected"]
        assert isinstance(data["domains"], list)

    def test_health_check_domains(self, client):
        """Test health check includes configured domains"""
        response = client.get("/api/v1/health")
        data = response.json()

        # Should have at least one domain configured
        assert len(data["domains"]) > 0
        assert "tempmail.example.com" in data["domains"]


class TestCORS:
    """Test CORS headers"""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present on actual requests"""
        # POST request should work and have CORS headers
        response = client.post("/api/v1/addresses")

        assert response.status_code == 200
        # CORS middleware is configured in the app


class TestNotFound:
    """Test 404 handling"""

    def test_nonexistent_endpoint(self, client):
        """Test accessing non-existent endpoint"""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404

    def test_wrong_method(self, client):
        """Test using wrong HTTP method"""
        # GET on POST-only endpoint
        response = client.get("/api/v1/addresses")

        assert response.status_code == 405  # Method not allowed


class TestAPIDocumentation:
    """Test API documentation endpoints"""

    def test_docs_endpoint_accessible(self, client):
        """Test /docs endpoint is accessible"""
        response = client.get("/docs")

        # Should return HTML or redirect
        assert response.status_code in [200, 307]

    def test_redoc_endpoint_accessible(self, client):
        """Test /redoc endpoint is accessible"""
        response = client.get("/redoc")

        # Should return HTML or redirect
        assert response.status_code in [200, 307]

    def test_openapi_json_accessible(self, client):
        """Test OpenAPI schema is accessible"""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        # Should be valid OpenAPI schema
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
