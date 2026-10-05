# Exercise Notes — Baseline Only

This file is for the exercise owner. Do not give these findings to the reverse-engineering agent before its first analysis.

Intentionally seeded examples include:

- Dynamic SQL in `reports.py`.
- Missing resource ownership check in `GET /api/orders/<id>`.
- Any authenticated user can modify product price in `PUT /api/products/<id>`.
- Hard-coded JWT fallback secret in `config.py`.
- Sensitive payment/card information written to logs.
- Detailed exception information returned by the global handler.
- Client-supplied `customer_id` is trusted in order creation for privileged flows.
- No explicit password policy or rate limiting.
- Debug defaults to true.

There are also non-security legacy issues: mixed responsibilities, global configuration, duplicated logic, weak domain boundaries, long route handlers, inconsistent error handling, and limited tests.

IMPORTANT: This is a training repository. Do not deploy it publicly or use real credentials/payment data.
