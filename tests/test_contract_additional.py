"""Additional API contract tests for expanded endpoints."""

from app.database import db
from app.flask_app import flask_app, init_database
from app.models import User


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.get_json()["data"]["access_token"]


def _create_admin_user():
    user = User(
        email="admin@test.com",
        full_name="Admin",
        role="admin",
        is_active=True,
        is_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()



def test_auth_profile_password_nafath_and_2fa():
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["TESTING"] = True
    with flask_app.app_context():
        db.drop_all()
        init_database(flask_app)

    client = flask_app.test_client()

    register = client.post(
        "/auth/register",
        json={
            "email": "newuser@test.com",
            "password": "password123",
            "full_name": "New User",
            "role": "customer",
        },
    )
    assert register.status_code == 201

    token = _login(client, "newuser@test.com", "password123")

    update = client.patch(
        "/auth/profile",
        headers=_auth_headers(token),
        json={"full_name": "Updated User"},
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["full_name"] == "Updated User"

    change_pw = client.post(
        "/auth/change-password",
        headers=_auth_headers(token),
        json={"old_password": "password123", "new_password": "password456"},
    )
    assert change_pw.status_code == 200

    verify_nafath = client.post(
        "/auth/verify-nafath",
        headers=_auth_headers(token),
        json={"national_id": "1234567890"},
    )
    assert verify_nafath.status_code == 200
    assert verify_nafath.get_json()["data"]["nafath_verified"] is True

    two_fa = client.post(
        "/auth/2fa",
        headers=_auth_headers(token),
        json={"enabled": True},
    )
    assert two_fa.status_code == 200
    assert two_fa.get_json()["data"]["two_factor_enabled"] is True



def test_admin_contract_endpoints():
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["TESTING"] = True
    with flask_app.app_context():
        db.drop_all()
        init_database(flask_app)
        _create_admin_user()

    client = flask_app.test_client()
    token = _login(client, "admin@test.com", "password123")
    headers = _auth_headers(token)

    assert client.get("/admin/dashboard/stats", headers=headers).status_code == 200
    assert client.get("/admin/users", headers=headers).status_code == 200
    assert client.get("/admin/customers", headers=headers).status_code == 200
    assert client.get("/admin/merchants", headers=headers).status_code == 200
    assert client.get("/admin/transactions", headers=headers).status_code == 200
    assert client.get("/admin/purchase-requests", headers=headers).status_code == 200
    assert client.get("/admin/settlements", headers=headers).status_code == 200
