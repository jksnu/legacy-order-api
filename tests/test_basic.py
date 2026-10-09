import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import jwt

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_DEBUG"] = "false"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-deployment"
os.environ["SEED_DEMO_DATA"] = "true"

from app import create_app
from database import db
from models import Customer, Order, OrderItem, Payment, Product
import routes as api_routes


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


def create_order_record(client, customer_email, total=100.0, created_at=None):
    with client.application.app_context():
        customer = Customer.query.filter_by(email=customer_email).first()
        product = Product.query.first()
        order = Order(
            customer_id=customer.id,
            status="NEW",
            total=total,
            created_at=created_at,
            notes="private order note",
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=1,
                unit_price=product.price,
            )
        )
        db.session.commit()
        return order.id


def customer_id_for(client, email):
    with client.application.app_context():
        return Customer.query.filter_by(email=email).first().id


def assert_denied(response):
    assert response.status_code in (403, 404)


def test_customer_list_and_self_detail_are_scoped(client):
    token = login(client, "alice@example.com", "alice123")
    headers = {"Authorization": f"Bearer {token}"}

    listing = client.get("/api/customers", headers=headers)
    assert listing.status_code == 200
    assert [customer["email"] for customer in listing.get_json()] == ["alice@example.com"]

    own_customer_id = customer_id_for(client, "alice@example.com")
    own_detail = client.get(f"/api/customers/{own_customer_id}", headers=headers)
    assert own_detail.status_code == 200
    assert own_detail.get_json()["email"] == "alice@example.com"


def test_customer_cannot_read_or_update_another_customer(client):
    token = login(client, "alice@example.com", "alice123")
    headers = {"Authorization": f"Bearer {token}"}
    bob_id = customer_id_for(client, "bob@example.com")

    assert_denied(client.get(f"/api/customers/{bob_id}", headers=headers))
    response = client.put(
        f"/api/customers/{bob_id}",
        json={"name": "Changed by Alice"},
        headers=headers,
    )
    assert_denied(response)
    with client.application.app_context():
        assert Customer.query.get(bob_id).name == "Bob Kumar"


def test_customer_can_read_own_order_but_not_another_users_order(client):
    order_id = create_order_record(client, "alice@example.com")
    alice_headers = {"Authorization": f"Bearer {login(client, 'alice@example.com', 'alice123')}"}
    bob_headers = {"Authorization": f"Bearer {login(client, 'bob@example.com', 'bob123')}"}

    own_response = client.get(f"/api/orders/{order_id}", headers=alice_headers)
    assert own_response.status_code == 200
    assert own_response.get_json()["notes"] == "private order note"
    assert_denied(client.get(f"/api/orders/{order_id}", headers=bob_headers))


def test_payment_read_is_scoped_to_order_owner(client):
    order_id = create_order_record(client, "alice@example.com")
    with client.application.app_context():
        db.session.add(
            Payment(
                order_id=order_id,
                amount=100.0,
                method="card",
                transaction_reference="test-reference",
            )
        )
        db.session.commit()

    alice_headers = {"Authorization": f"Bearer {login(client, 'alice@example.com', 'alice123')}"}
    bob_headers = {"Authorization": f"Bearer {login(client, 'bob@example.com', 'bob123')}"}
    assert client.get(f"/api/orders/{order_id}/payment", headers=alice_headers).status_code == 200
    assert_denied(client.get(f"/api/orders/{order_id}/payment", headers=bob_headers))


@pytest.mark.parametrize("action", ["status", "delete", "payment"])
def test_customer_cannot_mutate_another_users_order(client, action):
    order_id = create_order_record(client, "alice@example.com")
    bob_headers = {"Authorization": f"Bearer {login(client, 'bob@example.com', 'bob123')}"}

    if action == "status":
        response = client.put(
            f"/api/orders/{order_id}/status",
            json={"status": "CANCELLED"},
            headers=bob_headers,
        )
    elif action == "delete":
        response = client.delete(f"/api/orders/{order_id}", headers=bob_headers)
    else:
        response = client.post(
            f"/api/orders/{order_id}/payment",
            json={"amount": 100, "method": "card", "card_number": "123456789012"},
            headers=bob_headers,
        )

    assert_denied(response)
    with client.application.app_context():
        order = Order.query.get(order_id)
        assert order is not None
        assert order.status == "NEW"
        assert Payment.query.filter_by(order_id=order_id).count() == 0


def test_customer_cannot_create_order_for_another_customer(client):
    alice_customer_id = customer_id_for(client, "alice@example.com")
    with client.application.app_context():
        product_id = Product.query.order_by(Product.id).first().id
    bob_headers = {"Authorization": f"Bearer {login(client, 'bob@example.com', 'bob123')}"}

    response = client.post(
        "/api/orders",
        json={"customer_id": alice_customer_id, "items": [{"product_id": product_id, "quantity": 1}]},
        headers=bob_headers,
    )

    assert_denied(response)
    with client.application.app_context():
        assert Order.query.filter_by(customer_id=alice_customer_id).count() == 0


def test_customer_can_create_order_for_own_account(client):
    bob_headers = {"Authorization": f"Bearer {login(client, 'bob@example.com', 'bob123')}"}
    with client.application.app_context():
        product_id = Product.query.order_by(Product.id).first().id

    response = client.post(
        "/api/orders",
        json={"items": [{"product_id": product_id, "quantity": 1}]},
        headers=bob_headers,
    )

    assert response.status_code == 201
    with client.application.app_context():
        order = Order.query.get(response.get_json()["id"])
        bob_id = Customer.query.filter_by(email="bob@example.com").first().id
        assert order.customer_id == bob_id


def test_customer_cannot_update_product_but_admin_can(client):
    with client.application.app_context():
        product = Product.query.order_by(Product.id).first()
        product_id = product.id
        original_price = product.price
    customer_headers = {"Authorization": f"Bearer {login(client, 'alice@example.com', 'alice123')}"}
    admin_headers = {"Authorization": f"Bearer {login(client, 'admin@example.com', 'admin123')}"}

    denied = client.put(
        f"/api/products/{product_id}",
        json={"price": original_price + 1},
        headers=customer_headers,
    )
    assert_denied(denied)
    with client.application.app_context():
        assert Product.query.get(product_id).price == original_price

    allowed = client.put(
        f"/api/products/{product_id}",
        json={"price": original_price + 1},
        headers=admin_headers,
    )
    assert allowed.status_code == 200


def test_report_rejects_or_safely_treats_injection_shaped_date(client):
    create_order_record(client, "alice@example.com", created_at=datetime(1999, 1, 1))
    with client.application.app_context():
        old_order = Order.query.first()
        old_order.status = "OLD_ORDER"
        db.session.commit()
    admin_headers = {"Authorization": f"Bearer {login(client, 'admin@example.com', 'admin123')}"}
    payload = "2000-01-01' OR 1=1 -- "

    response = client.get(
        "/api/reports/sales",
        query_string={"start": payload, "end": "2100-01-01"},
        headers=admin_headers,
    )

    assert response.status_code in (200, 400)
    assert "OLD_ORDER" not in response.get_data(as_text=True)


def test_login_token_has_expiration_and_invalid_token_fails_closed(client):
    response = client.post("/api/login", json={"email": "alice@example.com", "password": "alice123"})
    assert response.status_code == 200
    token = response.get_json()["token"]
    claims = jwt.decode(
        token,
        os.environ["JWT_SECRET"],
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    assert "exp" in claims
    expired_token = jwt.encode(
        {"user_id": claims["user_id"], "role": "customer", "exp": 1},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

    invalid = client.get("/api/customers", headers={"Authorization": "Bearer not-a-valid-token"})
    assert invalid.status_code == 401
    expired = client.get("/api/customers", headers={"Authorization": f"Bearer {expired_token}"})
    assert expired.status_code == 401


def test_invalid_card_value_is_not_written_to_logs(client, caplog):
    order_id = create_order_record(client, "alice@example.com")
    alice_headers = {"Authorization": f"Bearer {login(client, 'alice@example.com', 'alice123')}"}
    card_like_value = "12345678901"

    response = client.post(
        f"/api/orders/{order_id}/payment",
        json={"amount": 100, "method": "card", "card_number": card_like_value},
        headers=alice_headers,
    )

    assert response.status_code == 400
    assert card_like_value not in caplog.text


def test_successful_demo_payment_is_not_marked_as_settled(client):
    order_id = create_order_record(client, "alice@example.com")
    alice_headers = {"Authorization": f"Bearer {login(client, 'alice@example.com', 'alice123')}"}

    response = client.post(
        f"/api/orders/{order_id}/payment",
        json={"amount": 100, "method": "card", "card_number": "123456789012"},
        headers=alice_headers,
    )

    assert response.status_code == 201
    assert response.get_json()["status"] == "SIMULATED"
    with client.application.app_context():
        payment = Payment.query.filter_by(order_id=order_id).one()
        assert payment.status == "SIMULATED"
        assert payment.transaction_reference.startswith("TXN-")


def test_default_configuration_is_fail_closed_and_does_not_seed_users():
    workspace = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("JWT_SECRET", None)
    env.pop("FLASK_DEBUG", None)
    env.pop("SEED_DEMO_DATA", None)
    env["DATABASE_URL"] = "sqlite:///:memory:"
    code = "import config"

    missing_secret = subprocess.run(
        [sys.executable, "-c", code],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_secret.returncode != 0
    assert "JWT_SECRET" in missing_secret.stderr

    env["JWT_SECRET"] = "isolated-test-signing-secret"
    inspect_defaults = subprocess.run(
        [
            sys.executable,
            "-c",
            "import config; assert config.DEBUG is False; assert config.SEED_DEMO_DATA is False",
        ],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )
    assert inspect_defaults.returncode == 0, inspect_defaults.stderr

    inspect_seed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app import app; from database import db; from models import User; "
            "ctx = app.app_context(); ctx.push(); print(User.query.count()); ctx.pop()",
        ],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )
    assert inspect_seed.returncode == 0, inspect_seed.stderr
    assert inspect_seed.stdout.strip().endswith("0")


def test_unexpected_error_response_does_not_expose_exception_details(client):
    @client.application.get("/_test/unexpected-error")
    def unexpected_error():
        raise RuntimeError("sensitive database connection detail")

    response = client.get("/_test/unexpected-error")

    assert response.status_code == 500
    assert b"sensitive database connection detail" not in response.data
    assert b"RuntimeError" not in response.data


def test_malformed_order_quantity_does_not_echo_value(client):
    alice_headers = {"Authorization": f"Bearer {login(client, 'alice@example.com', 'alice123')}"}
    with client.application.app_context():
        product_id = Product.query.order_by(Product.id).first().id

    response = client.post(
        "/api/orders",
        json={"items": [{"product_id": product_id, "quantity": "not-a-quantity"}]},
        headers=alice_headers,
    )

    assert response.status_code == 400
    assert "not-a-quantity" not in response.get_data(as_text=True)


def test_sales_report_error_does_not_expose_exception_details(client, monkeypatch):
    def fail_report():
        raise RuntimeError("sensitive database connection detail")

    monkeypatch.setattr(api_routes, "sales_report", fail_report)
    admin_headers = {"Authorization": f"Bearer {login(client, 'admin@example.com', 'admin123')}"}

    response = client.get("/api/reports/sales", headers=admin_headers)

    assert response.status_code == 500
    assert "sensitive database connection detail" not in response.get_data(as_text=True)
