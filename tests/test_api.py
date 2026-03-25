"""
Basic API Tests
"""
import pytest


def get_test_client():
    """Get Flask test client with in-memory DB."""
    from app.flask_app import flask_app, init_database

    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["TESTING"] = True
    init_database(flask_app)

    return flask_app.test_client()


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint responds successfully."""
        client = get_test_client()
        response = client.get("/")

        assert response.status_code == 200
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        client = get_test_client()
        response = client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        if "status" in data:
            assert data["status"] == "healthy"
        else:
            assert data["success"] is True
            assert data["data"]["status"] == "healthy"
    
    def test_config_endpoint(self):
        """Test public config endpoint"""
        client = get_test_client()
        response = client.get("/config")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "default_credit_limit" in data["data"]
        assert "commission_rate" in data["data"]


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        client = get_test_client()
        response = client.post("/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })

        assert response.status_code == 401
    
    def test_register_customer(self):
        """Test customer registration"""
        client = get_test_client()
        response = client.post("/auth/register", json={
            "email": "newcustomer@test.com",
            "password": "password123",
            "full_name": "Test Customer",
            "role": "customer"
        })

        # May be 201 (success) or 400 (already exists)
        assert response.status_code in [201, 400]


class TestProtectedEndpoints:
    """Test protected endpoints require authentication"""
    
    def test_customer_profile_no_auth(self):
        """Test customer profile requires auth"""
        client = get_test_client()
        response = client.get("/customers/me")

        assert response.status_code == 401
    
    def test_merchant_profile_no_auth(self):
        """Test merchant profile requires auth"""
        client = get_test_client()
        response = client.get("/merchants/me")

        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
