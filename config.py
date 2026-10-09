import os

# Legacy configuration: values are mixed between environment variables and hard-coded defaults.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///legacy_orders.db")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be configured")
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "false").lower() == "true"
TAX_RATE = 0.18
DEFAULT_PAGE_SIZE = 20
