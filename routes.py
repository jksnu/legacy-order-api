from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from models import User, Customer, Product, Order, OrderItem, Payment
from auth import create_token, current_user, login_required, admin_required
from utils import product_to_dict, validate_product_payload, log_payment_failure
from customer_utils import customer_to_dict, normalize_phone
from order_utils import create_order
from reports import sales_report

api = Blueprint("api", __name__, url_prefix="/api")


def _customer_ids_for_user(user):
    return [customer.id for customer in Customer.query.filter_by(user_id=user.id).all()]


def _order_for_user(order_id, user):
    order = Order.query.get_or_404(order_id)
    if user.role != "admin" and order.customer_id not in _customer_ids_for_user(user):
        return None
    return order


@api.post("/register")
def register():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")
    if not email or not password or not name:
        return jsonify({"error": "email, password and name are required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 409
    user = User(email=email, password=generate_password_hash(password), role="customer")
    db.session.add(user)
    db.session.flush()
    customer = Customer(name=name, email=email, phone=normalize_phone(data.get("phone")), address=data.get("address"), user_id=user.id)
    db.session.add(customer)
    db.session.commit()
    return jsonify({"id": user.id, "email": user.email}), 201


@api.post("/login")
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get("email")).first()
    if not user or not check_password_hash(user.password, data.get("password", "")):
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify({"token": create_token(user), "role": user.role})


@api.get("/customers")
@login_required
def customers():
    user = current_user()
    query = Customer.query if user.role == "admin" else Customer.query.filter_by(user_id=user.id)
    return jsonify([customer_to_dict(c) for c in query.all()])


@api.get("/customers/<int:customer_id>")
@login_required
def customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    user = current_user()
    if user.role != "admin" and c.user_id != user.id:
        return jsonify({"error": "Not found"}), 404
    return jsonify(customer_to_dict(c))


@api.post("/customers")
@login_required
def add_customer():
    data = request.get_json() or {}
    c = Customer(name=data.get("name", ""), email=data.get("email", ""), phone=normalize_phone(data.get("phone")), address=data.get("address"))
    db.session.add(c)
    db.session.commit()
    return jsonify(customer_to_dict(c)), 201


@api.put("/customers/<int:customer_id>")
@login_required
def update_customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    user = current_user()
    if user.role != "admin" and c.user_id != user.id:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    c.name = data.get("name", c.name)
    c.email = data.get("email", c.email)
    c.phone = normalize_phone(data.get("phone", c.phone))
    c.address = data.get("address", c.address)
    db.session.commit()
    return jsonify(customer_to_dict(c))


@api.delete("/customers/<int:customer_id>")
@admin_required
def delete_customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Customer deleted"})


@api.get("/products")
def products():
    return jsonify([product_to_dict(p) for p in Product.query.filter_by(active=True).all()])


@api.get("/products/<int:product_id>")
def product(product_id):
    p = Product.query.get_or_404(product_id)
    return jsonify(product_to_dict(p))


@api.post("/products")
@admin_required
def add_product():
    data = request.get_json() or {}
    errors = validate_product_payload(data)
    if errors:
        return jsonify({"errors": errors}), 400
    p = Product(name=data["name"], description=data.get("description"), price=float(data["price"]), stock=int(data.get("stock", 0)))
    db.session.add(p)
    db.session.commit()
    return jsonify(product_to_dict(p)), 201


@api.put("/products/<int:product_id>")
@admin_required
def update_product(product_id):
    p = Product.query.get_or_404(product_id)
    data = request.get_json() or {}
    if "name" in data:
        p.name = data["name"]
    if "price" in data:
        p.price = float(data["price"])
    if "stock" in data:
        p.stock = int(data["stock"])
    db.session.commit()
    return jsonify(product_to_dict(p))


@api.get("/orders")
@login_required
def orders():
    user = current_user()
    if user.role == "admin":
        all_orders = Order.query.order_by(Order.created_at.desc()).all()
    else:
        customer_ids = _customer_ids_for_user(user)
        all_orders = Order.query.filter(Order.customer_id.in_(customer_ids)).order_by(Order.created_at.desc()).all() if customer_ids else []
    return jsonify([{"id": o.id, "customer_id": o.customer_id, "status": o.status, "total": o.total} for o in all_orders])


@api.get("/orders/<int:order_id>")
@login_required
def get_order(order_id):
    o = _order_for_user(order_id, current_user())
    if o is None:
        return jsonify({"error": "Not found"}), 404
    items = OrderItem.query.filter_by(order_id=o.id).all()
    return jsonify({
        "id": o.id,
        "customer_id": o.customer_id,
        "status": o.status,
        "total": o.total,
        "notes": o.notes,
        "items": [{"product_id": i.product_id, "quantity": i.quantity, "unit_price": i.unit_price} for i in items],
    })


@api.post("/orders")
@login_required
def add_order():
    user = current_user()
    data = request.get_json() or {}
    customer_id = data.get("customer_id")
    if user.role != "admin":
        customer_ids = _customer_ids_for_user(user)
        if customer_id and customer_id not in customer_ids:
            return jsonify({"error": "Not found"}), 404
        customer_id = customer_id or (customer_ids[0] if customer_ids else None)
    if not customer_id or not data.get("items"):
        return jsonify({"error": "customer_id and items are required"}), 400
    try:
        order = create_order(customer_id, data["items"], data.get("notes"))
        return jsonify({"id": order.id, "total": order.total, "status": order.status}), 201
    except ValueError as exc:
        db.session.rollback()
        safe_messages = {
            "Product not found": "Product not found",
            "Quantity must be positive": "Quantity must be positive",
            "Insufficient stock": "Insufficient stock",
        }
        return jsonify({"error": safe_messages.get(str(exc), "Invalid order items")}), 400
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("Order creation failed error_type=%s", type(exc).__name__)
        return jsonify({"error": "Unable to create order"}), 500


@api.put("/orders/<int:order_id>/status")
@login_required
def update_order_status(order_id):
    o = _order_for_user(order_id, current_user())
    if o is None:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ["NEW", "PROCESSING", "SHIPPED", "CANCELLED"]:
        return jsonify({"error": "Invalid status"}), 400
    o.status = status
    db.session.commit()
    return jsonify({"id": o.id, "status": o.status})


@api.delete("/orders/<int:order_id>")
@login_required
def delete_order(order_id):
    o = _order_for_user(order_id, current_user())
    if o is None:
        return jsonify({"error": "Not found"}), 404
    OrderItem.query.filter_by(order_id=o.id).delete()
    Payment.query.filter_by(order_id=o.id).delete()
    db.session.delete(o)
    db.session.commit()
    return jsonify({"message": "Order deleted"})


@api.post("/orders/<int:order_id>/payment")
@login_required
def pay_order(order_id):
    o = _order_for_user(order_id, current_user())
    if o is None:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    amount = float(data.get("amount", 0))
    method = data.get("method", "card")
    card_number = data.get("card_number", "")
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400
    if amount != o.total:
        return jsonify({"error": "Payment amount must equal order total"}), 400
    if Payment.query.filter_by(order_id=o.id).first():
        return jsonify({"error": "Order already paid"}), 409
    if method == "card" and len(card_number) < 12:
        log_payment_failure(o.id)
        return jsonify({"error": "Invalid card number"}), 400
    payment = Payment(
        order_id=o.id,
        amount=amount,
        method=method,
        status="SIMULATED",
        transaction_reference="TXN-" + str(o.id) + "-001",
    )
    db.session.add(payment)
    o.status = "PROCESSING"
    db.session.commit()
    return jsonify({"payment_id": payment.id, "status": payment.status}), 201


@api.get("/orders/<int:order_id>/payment")
@login_required
def get_payment(order_id):
    payment = Payment.query.filter_by(order_id=order_id).first_or_404()
    order = _order_for_user(payment.order_id, current_user())
    if order is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"id": payment.id, "order_id": payment.order_id, "amount": payment.amount, "method": payment.method, "status": payment.status, "transaction_reference": payment.transaction_reference})


@api.get("/reports/sales")
@admin_required
def report_sales():
    try:
        return jsonify(sales_report())
    except Exception as exc:
        current_app.logger.error("Sales report failed error_type=%s", type(exc).__name__)
        return jsonify({"error": "Unable to generate sales report"}), 500
