import os

# Legacy configuration: values are mixed between environment variables and hard-coded defaults.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///legacy_orders.db")
JWT_SECRET = os.getenv("JWT_SECRET", "legacy-development-secret-change-me")
DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
TAX_RATE = 0.18
DEFAULT_PAGE_SIZE = 20
