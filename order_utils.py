from database import db
from models import Order, OrderItem, Product
from config import TAX_RATE


def calculate_order_total(items):
    subtotal = 0
    for item in items:
        product = Product.query.get(item["product_id"])
        if product:
            subtotal += product.price * item["quantity"]
    tax = subtotal * TAX_RATE
    return round(subtotal + tax, 2)


def create_order(customer_id, items, notes=None):
    order = Order(customer_id=customer_id, status="NEW", notes=notes or "")
    db.session.add(order)
    db.session.flush()

    total = 0
    for item in items:
        product = Product.query.get(item["product_id"])
        quantity = int(item["quantity"])
        if not product:
            raise ValueError("Product not found")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if product.stock < quantity:
            raise ValueError("Insufficient stock")
        product.stock -= quantity
        line_total = product.price * quantity
        total += line_total
        db.session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=quantity, unit_price=product.price))

    order.total = round(total * (1 + TAX_RATE), 2)
    db.session.commit()
    return order
