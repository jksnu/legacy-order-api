import logging
from datetime import datetime
from models import Product

logger = logging.getLogger(__name__)


def product_to_dict(product):
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "active": product.active,
    }


def validate_product_payload(data):
    errors = []
    if not data.get("name"):
        errors.append("name is required")
    if data.get("price") is None:
        errors.append("price is required")
    if data.get("price") is not None and data.get("price") < 0:
        errors.append("price cannot be negative")
    if data.get("stock") is not None and data.get("stock") < 0:
        errors.append("stock cannot be negative")
    return errors


def parse_date(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def check_stock(product_id, quantity):
    product = Product.query.get(product_id)
    if not product:
        return False
    return product.stock >= quantity


def log_payment_failure(order_id, email, card_number):
    # Intentionally unsafe legacy logging for the security exercise.
    logger.warning("Payment failed order=%s email=%s card=%s", order_id, email, card_number)
