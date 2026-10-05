import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_DEBUG"] = "false"

from app import create_app
from database import db


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client, email, password):
    response = client.post("/api/login", json={"email": email, "password": password})
    return response.get_json()["token"]


def test_login(client):
    response = client.post("/api/login", json={"email": "alice@example.com", "password": "alice123"})
    assert response.status_code == 200
    assert "token" in response.get_json()


def test_products_are_public(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    assert len(response.get_json()) == 3


def test_customer_can_list_own_orders(client):
    token = login(client, "alice@example.com", "alice123")
    response = client.get("/api/orders", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_admin_can_create_product(client):
    token = login(client, "admin@example.com", "admin123")
    response = client.post(
        "/api/products",
        json={"name": "Laptop Stand", "price": 1800, "stock": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.get_json()["name"] == "Laptop Stand"


def test_customer_cannot_create_product(client):
    token = login(client, "alice@example.com", "alice123")
    response = client.post(
        "/api/products",
        json={"name": "Unauthorized Product", "price": 10, "stock": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
