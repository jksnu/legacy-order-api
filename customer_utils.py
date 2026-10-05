from models import Customer


def customer_to_dict(customer):
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "user_id": customer.user_id,
    }


def normalize_phone(phone):
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit() or c == "+")


def find_customer_by_email(email):
    return Customer.query.filter_by(email=email).first()
