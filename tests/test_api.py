"""
Basic API Tests
"""
import pytest
from app.database import db
from app.flask_app import flask_app, init_database
from app.models import User, Customer, Merchant


@pytest.fixture
def client():
    """Get Flask test client with isolated in-memory DB."""
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["TESTING"] = True
    with flask_app.app_context():
        db.drop_all()
        init_database(flask_app)

    yield flask_app.test_client()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["data"]["access_token"]


def _seed_customer_and_merchant():
    with flask_app.app_context():
        customer_user = User(
            email="customer.seed@test.com",
            full_name="Seed Customer",
            phone="+966501111111",
            role="customer",
            is_active=True,
            is_verified=True,
        )
        customer_user.set_password("password123")
        db.session.add(customer_user)
        db.session.flush()

        customer = Customer(
            user_id=customer_user.id,
            credit_limit=5000.0,
            available_balance=5000.0,
            outstanding_balance=0.0,
            status="active",
        )
        db.session.add(customer)

        merchant_user = User(
            email="merchant.seed@test.com",
            full_name="Seed Merchant",
            phone="+966502222222",
            role="merchant",
            is_active=True,
            is_verified=True,
        )
        merchant_user.set_password("password123")
        db.session.add(merchant_user)
        db.session.flush()

        merchant = Merchant(
            user_id=merchant_user.id,
            shop_name="Seed Shop",
            status="active",
            is_verified=True,
        )
        db.session.add(merchant)
        db.session.commit()

        return {
            "customer_email": customer_user.email,
            "customer_code": customer.customer_code,
            "merchant_email": merchant_user.email,
            "password": "password123",
        }


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint responds successfully."""
        response = client.get("/")

        assert response.status_code == 200
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
    
    def test_config_endpoint(self, client):
        """Test public config endpoint"""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "default_credit_limit" in data["data"]
        assert "commission_rate" in data["data"]


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post("/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })

        assert response.status_code == 401
    
    def test_register_login_and_me_contract(self, client):
        """Test auth contract: register -> login -> me and invalid token."""
        response = client.post("/auth/register", json={
            "email": "newcustomer@test.com",
            "password": "password123",
            "full_name": "Test Customer",
            "role": "customer"
        })

        assert response.status_code == 201
        register_data = response.get_json()
        assert register_data["success"] is True
        assert register_data["data"]["user"]["role"] == "customer"

        token = _login(client, "newcustomer@test.com", "password123")
        me_response = client.get("/auth/me", headers=_auth_headers(token))
        assert me_response.status_code == 200
        me_data = me_response.get_json()
        assert me_data["success"] is True
        assert me_data["data"]["email"] == "newcustomer@test.com"

        invalid_me = client.get("/auth/me", headers=_auth_headers("bad-token"))
        assert invalid_me.status_code == 401


class TestProtectedEndpoints:
    """Test protected endpoints require authentication"""
    
    def test_customer_profile_no_auth(self, client):
        """Test customer profile requires auth"""
        response = client.get("/customers/me")

        assert response.status_code == 401
    
    def test_merchant_profile_no_auth(self, client):
        """Test merchant profile requires auth"""
        response = client.get("/merchants/me")

        assert response.status_code == 401


class TestCustomerCriticalFlow:
    """Contract tests for customer purchase and payment flow."""

    def test_customer_accept_and_pay_purchase_request(self, client):
        seed = _seed_customer_and_merchant()
        merchant_token = _login(client, seed["merchant_email"], seed["password"])
        customer_token = _login(client, seed["customer_email"], seed["password"])

        create_response = client.post(
            "/merchants/send-purchase-request",
            headers=_auth_headers(merchant_token),
            json={
                "customer_code": seed["customer_code"],
                "amount": 250,
                "description": "Laptop accessories",
            },
        )
        assert create_response.status_code == 201
        request_id = create_response.get_json()["data"]["id"]

        pending_response = client.get(
            "/customers/purchase-requests/pending",
            headers=_auth_headers(customer_token),
        )
        assert pending_response.status_code == 200
        pending_ids = [item["id"] for item in pending_response.get_json()["data"]]
        assert request_id in pending_ids

        accept_response = client.post(
            f"/customers/purchase-requests/{request_id}/accept",
            headers=_auth_headers(customer_token),
            json={},
        )
        assert accept_response.status_code == 200
        accept_data = accept_response.get_json()["data"]
        transaction_id = accept_data["transaction_id"]

        pay_response = client.post(
            f"/customers/transactions/{transaction_id}/pay",
            headers=_auth_headers(customer_token),
            json={"amount": 100, "payment_method": "card"},
        )
        assert pay_response.status_code == 200
        pay_data = pay_response.get_json()["data"]
        assert pay_data["amount_paid"] == 100.0
        assert pay_data["remaining_amount"] == 150.0

    def test_customer_reject_purchase_request(self, client):
        seed = _seed_customer_and_merchant()
        merchant_token = _login(client, seed["merchant_email"], seed["password"])
        customer_token = _login(client, seed["customer_email"], seed["password"])

        create_response = client.post(
            "/merchants/purchase-requests",
            headers=_auth_headers(merchant_token),
            json={
                "customer_code": seed["customer_code"],
                "amount": 120,
                "description": "Small appliance",
            },
        )
        assert create_response.status_code == 201
        request_id = create_response.get_json()["data"]["id"]

        reject_response = client.post(
            f"/customers/purchase-requests/{request_id}/reject",
            headers=_auth_headers(customer_token),
            json={},
        )
        assert reject_response.status_code == 200
        assert reject_response.get_json()["data"]["status"] == "rejected"


class TestMerchantCriticalFlow:
    """Contract tests for merchant lookup/request/listing endpoints."""

    def test_merchant_lookup_and_lists(self, client):
        seed = _seed_customer_and_merchant()
        merchant_token = _login(client, seed["merchant_email"], seed["password"])

        lookup_response = client.get(
            f"/merchants/lookup-customer/{seed['customer_code']}",
            headers=_auth_headers(merchant_token),
        )
        assert lookup_response.status_code == 200
        lookup_data = lookup_response.get_json()["data"]
        assert lookup_data["email"] == seed["customer_email"]
        assert lookup_data["customer_code"] == seed["customer_code"]

        create_response = client.post(
            "/merchants/send-purchase-request",
            headers=_auth_headers(merchant_token),
            json={
                "customer_code": seed["customer_code"],
                "amount": 90,
                "description": "Phone case",
            },
        )
        assert create_response.status_code == 201

        requests_response = client.get(
            "/merchants/purchase-requests",
            headers=_auth_headers(merchant_token),
        )
        assert requests_response.status_code == 200
        assert isinstance(requests_response.get_json()["data"], list)

        transactions_response = client.get(
            "/merchants/transactions",
            headers=_auth_headers(merchant_token),
        )
        assert transactions_response.status_code == 200

        settlements_response = client.get(
            "/merchants/settlements",
            headers=_auth_headers(merchant_token),
        )
        assert settlements_response.status_code == 200


class TestAdminCriticalFlow:
    """Contract tests for admin stats and test-data endpoint behavior."""

    def test_admin_stats_and_create_test_data(self, client):
        stats_response = client.get("/admin/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.get_json()
        assert stats_data["success"] is True

        create_first = client.get("/admin/create-test-data")
        assert create_first.status_code == 200
        first_data = create_first.get_json()
        assert first_data["success"] is True

        create_second = client.get("/admin/create-test-data")
        assert create_second.status_code == 200
        second_data = create_second.get_json()
        assert second_data["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
