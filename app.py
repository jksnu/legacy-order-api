from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from config import DATABASE_URL, DEBUG, SEED_DEMO_DATA
from database import init_db, db
from models import User, Customer, Product, Order, OrderItem, Payment
from routes import api
from werkzeug.security import generate_password_hash


def create_app():
    app = Flask(__name__)
    app.config["DATABASE_URL"] = DATABASE_URL
    app.config["DEBUG"] = DEBUG
    init_db(app)
    app.register_blueprint(api)

    @app.errorhandler(Exception)
    def handle_error(error):
        if isinstance(error, HTTPException):
            return jsonify({"error": error.name}), error.code or 500
        app.logger.error("Unhandled request error type=%s", type(error).__name__)
        return jsonify({"error": "Internal server error"}), 500

    with app.app_context():
        db.create_all()
        if SEED_DEMO_DATA:
            seed_data()

    return app


def seed_data():
    if User.query.count() > 0:
        return

    admin = User(email="admin@example.com", password=generate_password_hash("admin123"), role="admin")
    alice = User(email="alice@example.com", password=generate_password_hash("alice123"), role="customer")
    bob = User(email="bob@example.com", password=generate_password_hash("bob123"), role="customer")
    db.session.add_all([admin, alice, bob])
    db.session.flush()

    c1 = Customer(name="Alice Sharma", email="alice@example.com", phone="+919876543210", address="Bengaluru", user_id=alice.id)
    c2 = Customer(name="Bob Kumar", email="bob@example.com", phone="+919876543211", address="Chennai", user_id=bob.id)
    db.session.add_all([c1, c2])

    p1 = Product(name="Mechanical Keyboard", description="Compact keyboard", price=3500.0, stock=50, active=True)
    p2 = Product(name="Wireless Mouse", description="Ergonomic mouse", price=1200.0, stock=100, active=True)
    p3 = Product(name="USB-C Hub", description="7-in-1 hub", price=2500.0, stock=30, active=True)
    db.session.add_all([p1, p2, p3])
    db.session.commit()


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"])
