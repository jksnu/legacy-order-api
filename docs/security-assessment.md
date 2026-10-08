# Executive Summary

Independent review of the current Flask API found confirmed access-control defects, SQL injection in sales reporting, a repository-known JWT key fallback, non-expiring bearer tokens, and a payment workflow that records `PAID` without in-repository payment verification. Startup also defaults debug on and seeds documented development credentials into an empty database. The application hashes passwords with Werkzeug, but that does not mitigate the authorization and token/key issues.

There are **11 findings**: A01 (4), A02 (1), A03 (1), A04 (1), A05 (2), A07 (1), and A09 (1). Eight are High, two Medium, and one Low; none is rated Critical because reachable production deployment and downstream payment behavior are not established. No finding was identified from available evidence for A06, A08, or A10. This is not a claim that those categories are secure. The most urgent confirmed issues are cross-account access and mutation, admin access if known defaults remain active, and report SQL injection after admin access.

No application source, test, dependency, or configuration file was modified. Only this document is being created.

# Security Posture Overview

## Scope and Method

Reviewed repository application modules, routes, models, configuration, README, dependency declarations, tests, and startup behavior. No prior analysis or seed notes were used. This is source-based assessment; no live penetration test, production configuration inspection, external infrastructure review, CVE database query, or database-content inspection was performed. Deployment-dependent conditions are identified as Unknown.

## Observed Controls and Gaps

- Registration hashes passwords with Werkzeug; login checks the hash and returns a PyJWT HS256 bearer token.
- Token decoding uses an HS256 allowlist and reloads the user from the database, but token creation has no expiration claim and a fixed secret fallback exists.
- Admin checks are applied to some endpoints, but customer/order ownership checks and write-role checks are inconsistent.
- SQLAlchemy ORM is used for most database operations. The sales report builds SQL using concatenated request parameters.
- Payment is represented by a local row; no payment gateway or verification integration is visible.
- Customer/order/payment responses include personal or business data. Object-level authorization is missing on several paths.
- No source-level rate limiter, authentication lockout, security-header policy, TLS setup, monitoring integration, or body/resource limits were found. Whether the deployment supplies these is Unknown.
- An application-wide exception handler returns exception strings. A logger records a card-like input on one validation failure path.

## Severity and Confidence

Severity and likelihood are qualitative, based on the demonstrated code path and stated preconditions. Confidence describes evidence in the repository, not confidence about a deployment that was not inspected. High findings can have conditional deployment exposure. Remediation priority maps High to P1, Medium to P2, Low to P3, and Critical to P0 as requested.

# OWASP Top 10 Assessment

| Category | Assessment | Summary |
|---|---|---|
| A01 Broken Access Control | Finding identified | Cross-customer reads/updates, order BOLA and mutations, caller-selected order customer IDs, and customer-role product changes. SEC-001 through SEC-004. |
| A02 Cryptographic Failures | Finding identified | Fixed JWT signing-secret fallback can undermine signature authenticity if used. SEC-006. |
| A03 Injection | Finding identified | `start` and `end` query parameters are concatenated into sales-report SQL. SEC-008. |
| A04 Insecure Design | Finding identified | Payment is stored as paid based on client values without verification visible in this repository. SEC-009. |
| A05 Security Misconfiguration | Finding identified | Debug defaults on, documented development users are seeded, and exception text is returned. SEC-010 and SEC-011. |
| A06 Vulnerable and Outdated Components | No finding identified from available evidence | No specific CVE is asserted; no advisory database or resolved dependency inventory was assessed. Current vulnerability status is Unable to determine. |
| A07 Identification and Authentication Failures | Finding identified | JWTs have no expiration or source-enforced lifetime. SEC-007. |
| A08 Software and Data Integrity Failures | No finding identified from available evidence | No untrusted artifact/update path or integrity-check bypass was established from source. |
| A09 Security Logging and Monitoring Failures | Finding identified | Failed card validation logs the submitted card-like value. SEC-005. Actual sink, access, and retention are Unknown. |
| A10 Server-Side Request Forgery | No finding identified from available evidence | No user-controlled URL fetch or server-side HTTP request path was found; `requests` is declared but not imported by application code. |

# Detailed Findings

## SEC-001: Customer Data Is Not Scoped to the Authenticated User

1. **Finding ID:** SEC-001
2. **Title:** Customer list, detail, and update permit cross-customer access
3. **OWASP Top 10 category:** A01 Broken Access Control
4. **Affected endpoint(s):** `GET /api/customers`, `GET /api/customers/<customer_id>`, `PUT /api/customers/<customer_id>`
5. **Affected file(s):** `routes.py`, `models.py`
6. **Vulnerable code/function:** `customers`, `customer`, `update_customer`
7. **Evidence from the repository:** Each handler only uses `login_required`. `customers` returns `Customer.query.all()`; detail and update load a row by supplied ID. `Customer.user_id` exists, but these handlers do not compare it to the authenticated user.
8. **Data/control flow:** A bearer-authenticated caller lists all customers or supplies another record ID; the handler serializes or commits changes without an ownership check.
9. **Preconditions:** Valid user token and reachable endpoint; targeted operations need a customer ID that is known or guessed.
10. **Potential impact:** Disclosure or modification of customer names, email, phone, address, and linked user ID.
11. **Likelihood:** High
12. **Severity:** High
13. **Confidence:** High
14. **Recommended remediation direction:** Enforce ownership or explicit administrator policy for each customer operation; derive identity from the authenticated principal and test cross-account denial.

**Classification:** Confirmed broken object-level authorization. **Mapping rationale:** Access to the requested resource is not constrained by the caller's relationship to that customer.

## SEC-002: Order and Payment Reads Lack Ownership Checks

1. **Finding ID:** SEC-002
2. **Title:** Any authenticated user can retrieve order and payment details by ID
3. **OWASP Top 10 category:** A01 Broken Access Control
4. **Affected endpoint(s):** `GET /api/orders/<order_id>`, `GET /api/orders/<order_id>/payment`
5. **Affected file(s):** `routes.py`
6. **Vulnerable code/function:** `get_order`, `get_payment`
7. **Evidence from the repository:** Both routes require only `login_required`. `get_order` returns customer ID, order status, total, notes, and item details. `get_payment` returns amount, method, status, and transaction reference. Neither checks ownership. A source comment in `get_order` explicitly notes missing ownership verification.
8. **Data/control flow:** Caller supplies an order ID; ORM lookup returns it; the response serializes the order/payment without comparing its customer to the caller.
9. **Preconditions:** Valid bearer token, reachable endpoint, and known or guessable order ID.
10. **Potential impact:** Cross-customer disclosure of order contents, notes, totals, and payment metadata. The model does not store a full card number.
11. **Likelihood:** High
12. **Severity:** High
13. **Confidence:** High
14. **Recommended remediation direction:** Apply object-level ownership or administrator authorization to order and nested payment reads; test using separate customer accounts.

**Classification:** Confirmed BOLA/IDOR pattern. **Mapping rationale:** Authentication is treated as sufficient to read resources belonging to another customer.

## SEC-003: Order Creation and Mutations Cross Customer Boundaries

1. **Finding ID:** SEC-003
2. **Title:** Customer can select another customer for order creation and mutate orders without ownership checks
3. **OWASP Top 10 category:** A01 Broken Access Control
4. **Affected endpoint(s):** `POST /api/orders`, `PUT /api/orders/<order_id>/status`, `DELETE /api/orders/<order_id>`, `POST /api/orders/<order_id>/payment`
5. **Affected file(s):** `routes.py`
6. **Vulnerable code/function:** `add_order`, `update_order_status`, `delete_order`, `pay_order`
7. **Evidence from the repository:** `add_order` trusts a truthy client-supplied `customer_id` for non-admin users and looks up the caller's customer only when the supplied ID is falsey. Status/delete/payment handlers require login and load target orders by ID without checking owner/admin rights. Delete removes items and payments; payment creates a local record and changes status.
8. **Data/control flow:** A customer supplies another customer ID during creation, or an order ID to a mutating handler; ORM updates/deletes are committed without an ownership comparison.
9. **Preconditions:** Valid token and reachable handler. Creation additionally needs a valid customer ID and non-empty items; mutation requires a target order ID. Payment also requires a positive amount equal to total, no existing payment, and a card string of at least 12 characters when method is `card`.
10. **Potential impact:** Misattributed orders, unauthorized status changes/deletion, and payment-state changes to another customer's order. No fund transfer is claimed; no processor call is present.
11. **Likelihood:** High
12. **Severity:** High
13. **Confidence:** High
14. **Recommended remediation direction:** Derive customer ID from authenticated identity for non-admins; enforce owner/admin policy on every order mutation and nested payment operation; test cross-account attempts.

**Classification:** Confirmed horizontal authorization defects. **Mapping rationale:** Callers cross customer ownership and role boundaries for order creation and mutation.

## SEC-004: Product Update Is Allowed for Any Authenticated Role

1. **Finding ID:** SEC-004
2. **Title:** Customer-role callers can alter product name, price, and stock
3. **OWASP Top 10 category:** A01 Broken Access Control
4. **Affected endpoint(s):** `PUT /api/products/<product_id>`
5. **Affected file(s):** `routes.py`
6. **Vulnerable code/function:** `update_product`
7. **Evidence from the repository:** The route uses `login_required`, then updates `name`, `price`, and `stock` from request JSON and commits. Product creation on the adjacent route requires `admin_required`.
8. **Data/control flow:** A customer obtains a normal token and sends a PUT for a product; route writes the supplied fields without checking the user's role.
9. **Preconditions:** Valid customer-role token and product ID.
10. **Potential impact:** Catalog integrity and pricing manipulation; modified price is used when new orders are calculated.
11. **Likelihood:** High
12. **Severity:** High
13. **Confidence:** High
14. **Recommended remediation direction:** Restrict catalog writes to an explicit administrative role and test denial for customer tokens.

**Classification:** Confirmed vertical privilege-boundary defect. **Mapping rationale:** A lower-privilege principal can mutate a resource managed through an admin-only create path.

## SEC-005: Failed Payment Validation Logs Card-Like Input

1. **Finding ID:** SEC-005
2. **Title:** Payment failure logger records the submitted card-like value
3. **OWASP Top 10 category:** A09 Security Logging and Monitoring Failures
4. **Affected endpoint(s):** `POST /api/orders/<order_id>/payment`, invalid-card branch
5. **Affected file(s):** `routes.py`, `utils.py`
6. **Vulnerable code/function:** `pay_order`, `log_payment_failure`
7. **Evidence from the repository:** For method `card` and `len(card_number) < 12`, `pay_order` passes the supplied value to `log_payment_failure`; the logger formats it as `card=%s`.
8. **Data/control flow:** Request JSON supplies the value, and the invalid-length branch sends it unchanged to a warning logger. This path logs values shorter than 12 characters, not a complete valid-length card number. Log sink and retention are not shown.
9. **Preconditions:** Authenticated caller, accessible order, positive matching amount, no prior payment, and short card-like input.
10. **Potential impact:** Card-like fragments or other sensitive strings may be retained in logs. Full card number exposure or unauthorized log access is not established.
11. **Likelihood:** Medium
12. **Severity:** Low
13. **Confidence:** High that the value is logged; Low that this specific path exposes a complete credential or reaches an insecure sink.
14. **Recommended remediation direction:** Do not log payment account input; log a fixed reason and non-sensitive correlation data; review log access and retention.

**Classification:** Confirmed logging weakness; actual sensitivity/exposure is conditional. **Mapping rationale:** Payment-related request data is recorded without redaction; operational monitoring failure itself is not established.

## SEC-006: JWT Signing Secret Has a Fixed Fallback

1. **Finding ID:** SEC-006
2. **Title:** Repository-known JWT signing secret is used when configuration is absent
3. **OWASP Top 10 category:** A02 Cryptographic Failures
4. **Affected endpoint(s):** All bearer-token protected endpoints
5. **Affected file(s):** `config.py`, `auth.py`
6. **Vulnerable code/function:** `JWT_SECRET`, `create_token`, `current_user`
7. **Evidence from the repository:** `config.py` falls back to `legacy-development-secret-change-me`. `auth.py` signs and verifies HS256 tokens using this value if no environment override is present. The token role claim is not the authorization source; the database user role is loaded.
8. **Data/control flow:** If the fallback is active, someone who knows the repository value can sign a token for an existing user ID. The app verifies it and looks up that user. An existing administrator ID is required for admin access.
9. **Preconditions:** Deployment uses the fallback, attacker can reach protected routes, and a valid user ID is known or inferred. A secret override unknown to the attacker blocks this specific path.
10. **Potential impact:** Authentication as a selected existing user, potentially an administrator.
11. **Likelihood:** High if default is active; otherwise deployment-dependent.
12. **Severity:** High
13. **Confidence:** High for source behavior; Medium for deployment configuration.
14. **Recommended remediation direction:** Require a high-entropy key from protected configuration, fail startup if missing, and rotate/invalidate tokens if the fallback may have been used.

**Classification:** Confirmed key-management weakness; production exploitability is conditional. **Mapping rationale:** A repository-known symmetric key undermines JWT signature authenticity, supporting A02.

## SEC-007: JWTs Have No Expiration

1. **Finding ID:** SEC-007
2. **Title:** Bearer tokens have no source-enforced lifetime
3. **OWASP Top 10 category:** A07 Identification and Authentication Failures
4. **Affected endpoint(s):** All routes guarded by `login_required` or `admin_required`
5. **Affected file(s):** `auth.py`
6. **Vulnerable code/function:** `create_token`, `current_user`
7. **Evidence from the repository:** `create_token` includes `user_id` and `role` but no `exp`; `current_user` does not require or check expiration.
8. **Data/control flow:** A copied token continues to authenticate while the signing key remains unchanged and its database user exists. No source-side revocation list is present.
9. **Preconditions:** Attacker obtains a valid token and the account/key remain valid; external expiry controls are not evidenced.
10. **Potential impact:** Stolen token replay can persist for an unbounded period at the application layer.
11. **Likelihood:** Medium
12. **Severity:** Medium
13. **Confidence:** High
14. **Recommended remediation direction:** Add and require expiration, define renewal and revocation/session invalidation, and protect tokens in transit and client storage.

**Classification:** Confirmed token-lifetime weakness. **Mapping rationale:** Unbounded bearer-token validity increases authentication replay risk under A07.

## SEC-008: Sales Report SQL Injection

1. **Finding ID:** SEC-008
2. **Title:** Sales-report date parameters are concatenated into SQL
3. **OWASP Top 10 category:** A03 Injection
4. **Affected endpoint(s):** `GET /api/reports/sales?start=...&end=...`
5. **Affected file(s):** `reports.py`, `routes.py`
6. **Vulnerable code/function:** `sales_report`, called by `report_sales`
7. **Evidence from the repository:** `sales_report` reads `start` and `end` from the request, concatenates them into quoted SQL, wraps it in `text()`, and executes it. The route requires admin, but the values remain caller-controlled.
8. **Data/control flow:** Request values become part of SQL source code and are submitted to the configured database connection.
9. **Preconditions:** Admin access and a crafted value accepted by the active database/driver. Exact payload behavior was not tested.
10. **Potential impact:** Query manipulation, disclosure of data available to the DB account, or query errors/availability impact. Exact impact is dialect-dependent.
11. **Likelihood:** Medium
12. **Severity:** High
13. **Confidence:** High for unsafe construction; Medium for precise payload impact.
14. **Recommended remediation direction:** Bind date parameters, parse/validate date values, keep SQL structure static, and test against the deployed database engine.

**Classification:** Confirmed injection vulnerability in query construction; impact depends on runtime database details. **Mapping rationale:** Request-controlled text is inserted into SQL syntax rather than bound as data.

## SEC-009: Payment Is Marked Paid Without In-Repository Verification

1. **Finding ID:** SEC-009
2. **Title:** Client values create a locally paid payment record
3. **OWASP Top 10 category:** A04 Insecure Design
4. **Affected endpoint(s):** `POST /api/orders/<order_id>/payment`
5. **Affected file(s):** `routes.py`, `models.py`
6. **Vulnerable code/function:** `pay_order`; `Payment.status` default
7. **Evidence from the repository:** The route checks positive amount/equality to order total and, for card method, only card-string length. It creates a payment with a predictable reference and commits. `Payment.status` defaults to `PAID`. No processor call, verified callback, or external authorization exists in the source.
8. **Data/control flow:** An authenticated caller submits matching amount and a sufficiently long card-like string; the route persists a payment state that serializes as paid without repository-visible verification.
9. **Preconditions:** Valid token, accessible order, exact positive total, no prior payment, and for card method a string at least 12 characters long. Other method values are not visibly allowlisted.
10. **Potential impact:** Downstream consumers may treat an unpaid order as settled. Actual fulfillment or financial loss is Unknown because no downstream consumer or payment processor is present.
11. **Likelihood:** Medium
12. **Severity:** High if downstream systems trust `PAID`; otherwise Medium. High is assigned pending confirmation of consumers.
13. **Confidence:** High that local paid state is written without in-repository verification; Medium for downstream impact.
14. **Recommended remediation direction:** Define payment lifecycle semantics; set paid only after trusted processor confirmation; validate methods and use verified idempotent transaction references.

**Classification:** Confirmed payment-state design weakness; external business impact is conditional. **Mapping rationale:** Client-controlled assertions are treated as proof of a financial state transition, a trust-boundary design failure.

## SEC-010: Debug and Seeded Development Accounts Are Defaults

1. **Finding ID:** SEC-010
2. **Title:** Debug defaults on and startup seeds documented credentials
3. **OWASP Top 10 category:** A05 Security Misconfiguration
4. **Affected endpoint(s):** `POST /api/login`, authenticated/admin endpoints, and direct startup via `python app.py`
5. **Affected file(s):** `config.py`, `app.py`, `README.md`
6. **Vulnerable code/function:** `DEBUG`, `create_app`, `seed_data`, direct-run block
7. **Evidence from the repository:** Missing `FLASK_DEBUG` evaluates to true. Direct execution passes that value to `app.run`. Startup calls `seed_data`; an empty user table receives admin/customer users with fixed passwords that README documents. The direct runner binds to `127.0.0.1`.
8. **Data/control flow:** A fresh database receives known accounts that can log in. Debug is enabled for direct execution absent an override; remote reachability depends on deployment/proxy behavior. Loopback binding applies to the shown direct runner only.
9. **Preconditions:** Seeded admin remains unchanged and API is reachable; debug exposure additionally requires a deployment that makes the debug server reachable beyond trusted local use.
10. **Potential impact:** Administrative access using known credentials or debugger exposure if remotely reachable. Remote debugger exposure is not claimed for an uninspected deployment.
11. **Likelihood:** Medium
12. **Severity:** High if reachable with defaults; lower in isolated local training use.
13. **Confidence:** High for source defaults; Medium for deployed exposure.
14. **Recommended remediation direction:** Disable debug by default and in production; separate demo seeding from normal startup; securely provision one-time admin credentials and remove known defaults.

**Classification:** Confirmed unsafe startup/configuration behavior; exploitability is deployment-dependent. **Mapping rationale:** Insecure debug and seed defaults are configuration mistakes under A05.

## SEC-011: Exception Responses Return Internal Error Text

1. **Finding ID:** SEC-011
2. **Title:** API responses include exception messages
3. **OWASP Top 10 category:** A05 Security Misconfiguration
4. **Affected endpoint(s):** Routes that raise uncaught exceptions; `POST /api/orders` and `GET /api/reports/sales` local exception paths
5. **Affected file(s):** `app.py`, `routes.py`
6. **Vulnerable code/function:** `handle_error`, `add_order`, `report_sales`
7. **Evidence from the repository:** The global handler returns `str(error)` and exception class with status 500. Order and report handlers also return `str(exc)`.
8. **Data/control flow:** A request triggers an exception and its message is serialized into the HTTP response. Message contents depend on the exception, framework, and DB.
9. **Preconditions:** Reachable route and an input or server condition that causes an exception.
10. **Potential impact:** Error text can reveal implementation or database details useful for follow-on attacks. No specific secret disclosure is established.
11. **Likelihood:** Medium
12. **Severity:** Medium
13. **Confidence:** High that messages are returned; Medium that a given message reveals sensitive internals.
14. **Recommended remediation direction:** Return generic stable client errors with correlation IDs; log detailed exceptions server-side with redaction and access control.

**Classification:** Confirmed error-information exposure weakness; sensitivity of individual messages is conditional. **Mapping rationale:** Returning internal exception details is an insecure error-handling configuration issue.

# Authentication and Authorization Analysis

## Authentication

Registration/login are public POST endpoints. Passwords are hashed and verified with Werkzeug. JWTs use HS256; the decoder explicitly allows HS256 and resolves `user_id` against the current database user. Token role is present but `admin_required` checks the database role, so changing only the role claim cannot grant admin privileges. There is no expiration claim, required expiry check, issuer/audience policy, revocation list, or password reset/MFA implementation in the repository. The static secret and unbounded lifetime are SEC-006/SEC-007. Whether proxy/TLS/client storage controls exist is Unknown.

## Authorization and Privilege Boundaries

- `admin_required`: customer delete, product create, sales report.
- `login_required` only: customer list/detail/create/update; product update; order list/detail/create/status/delete; payment create/read.
- Customer list returns every customer; detail/update use caller-provided IDs without checking `Customer.user_id` (SEC-001).
- Non-admin order listing is scoped, but order detail/payment reads are not (SEC-002); order creation trusts a truthy client customer ID and order mutations omit owner checks (SEC-003).
- Customer users can update product fields despite product creation being admin-only (SEC-004).
- Horizontal escalation is supported by object-ID lookups lacking ownership checks. Vertical escalation is supported by customer-role product writes. The report injection route is admin-only; admin access is a precondition for SEC-008.
- `current_user` catches all token decode/lookup exceptions and returns `None`; no auth bypass is demonstrated by this behavior.

Tests cover a successful login, product list, order-list success, admin product creation, and customer denial of product creation. Tests do not exercise token expiry/tampering, cross-account access, product update authorization, order ownership, or report injection.

# Input and Injection Analysis

- **SQL:** `reports.sales_report` is the only raw SQL construction observed. It concatenates request date parameters (SEC-008). Other observed database access uses SQLAlchemy ORM filters/lookups, which bind values.
- **Command/template/deserialization:** No subprocess/shell execution, dynamic template rendering, `eval`, `exec`, pickle, or YAML loading path was found.
- **Request parsing:** Routes generally use `request.get_json() or {}`. Validation varies. Product update, order creation, and payment directly cast/index request values; malformed types can raise exceptions. No code execution path is established, but error disclosure is assessed as SEC-011.
- **Resource controls:** No application-level rate limiting, login lockout, general body-size cap, pagination, or resource-use limit was found. External proxy/server controls are Unknown. Login/register brute force risk is a hardening concern, not a confirmed separate finding.
- **SSRF:** No user-controlled URL fetch or outbound HTTP call is present. Declared `requests` is not imported in application source.

# Secrets and Sensitive Data Analysis

- `JWT_SECRET` has a fixed development fallback (SEC-006); whether deployment overrides it is Unknown.
- `app.py` seeds fixed admin and customer passwords when there are no users; README publishes them (SEC-010). DB password values are stored as Werkzeug hashes, not plaintext.
- Login returns bearer tokens in JSON; explicit token logging was not found. Expiry is absent (SEC-007). Client storage and TLS are Unknown.
- `Customer` responses expose names, email, phone, address, and user ID; order responses expose notes, product/quantity/price data, and totals; payment responses expose amount, method, status, and reference. Access-control findings describe who can reach them.
- `Payment` has no card-number column. The invalid-card branch logs values shorter than 12 characters; full PAN logging is not demonstrated (SEC-005).
- Exception text is returned to clients (SEC-011); no specific secret in a response has been proven.
- No external API key, cloud credential, or DB password appears in source. Actual environment secrets are Unknown.

# Dependency Analysis

`requirements.txt` pins Flask 3.0.3, Flask-SQLAlchemy 3.1.1, PyJWT 2.9.0, Werkzeug 3.0.4, pytest 8.3.3, and requests 2.32.3. `requests` is not imported by application source. SQLAlchemy APIs are used, and SQLAlchemy is supplied through Flask-SQLAlchemy rather than pinned as a direct requirement.

No lockfile/full resolved dependency tree was reviewed and no current advisory database was queried. No known CVE is asserted. Current vulnerability status for the pinned components is **Unable to determine from evidence gathered**. Deprecation warnings observed for `Query.get()` and `datetime.utcnow()` are not CVE evidence.

# Logging and Monitoring Analysis

The explicit application logger is `utils.log_payment_failure`; it logs order ID, email, and the submitted card-like value on the short-input validation branch (SEC-005). The value is under 12 characters on that path. No audit events, auth-denial events, monitoring, alerting, or application logging configuration were found. Log sink, redaction, access controls, retention, and external monitoring are Unknown. No operational monitoring failure is inferred solely from their absence in this repository.

# Risk Prioritization

Priority mapping: Critical = P0, High = P1, Medium = P2, Low = P3. Likelihood and confidence are qualitative as described above.

The complete prioritized summary is provided in the final table at the end of this document.

# Recommended Remediation Sequence

1. Verify deployment configuration and reachability immediately: determine whether the fixed JWT fallback, seeded credentials, or debug mode are active; rotate/remove exposed identities and secrets.
2. Enforce per-object ownership and role policies for customer, order, payment, and product operations. Derive non-admin customer IDs from authenticated identity. Add cross-account/role tests.
3. Replace SQL concatenation with bound parameters and validated date values; test against the configured database engine.
4. Define payment lifecycle semantics; mark payments paid only after trusted verification if downstream behavior depends on settlement.
5. Remove card-like values from logs, assess existing log exposure, and return generic client errors while keeping protected server-side diagnostics.
6. Require secure JWT signing-key configuration, define token expiry/revocation, disable debug by default, and separate demo seed data from ordinary startup.
7. Add tests for token lifecycle, access control, report injection-shaped input, payment-state behavior, and error responses.
8. Perform an up-to-date dependency advisory scan against a complete resolved dependency inventory; do not infer CVEs from age or deprecation warnings.

# Evidence and Traceability

- `routes.py`: registration/login, customer/product endpoints, order list/detail/create/status/delete, payment handlers, and report handler establish the request paths and guards.
- `auth.py`: token creation/decoding, current-user lookup, and login/admin decorators.
- `config.py`: database, JWT-secret, and debug defaults.
- `app.py`: app creation, exception handler, seeding, module-level app, and direct-run behavior.
- `models.py`: user/customer/product/order/item/payment fields, foreign keys, and payment status default.
- `reports.py`: report parameters, SQL concatenation, and execution.
- `utils.py`: payment failure logging and product validation.
- `customer_utils.py`: customer serialization and phone normalization.
- `order_utils.py`: order creation, stock changes, and local transaction behavior.
- `database.py`: SQLAlchemy initialization.
- `requirements.txt`: declared package pins; `README.md`: documented development accounts and run instructions.
- `tests/test_basic.py`, `pytest.ini`: test coverage and discovery behavior.
- `instance/legacy_orders.db`: a database artifact exists. Its contents and sensitivity were not inspected; whether it contains personal or production data is Unknown.

No prior assessment or seed-note content was used as evidence.

| ID | OWASP | Finding | Severity | Likelihood | Confidence | Remediation Priority |
|---|---|---|---|---|---|---|
| SEC-001 | A01 | Customer records lack ownership scoping | High | High | High | P1 |
| SEC-002 | A01 | Order/payment reads lack ownership authorization | High | High | High | P1 |
| SEC-003 | A01 | Order creation and mutations cross ownership boundaries | High | High | High | P1 |
| SEC-004 | A01 | Customer role can mutate product catalog | High | High | High | P1 |
| SEC-005 | A09 | Failed payment path logs card-like input | Low | Medium | High code / Low exposure | P3 |
| SEC-006 | A02 | Fixed JWT signing-secret fallback | High | High if default active | High code / Medium deployment | P1 |
| SEC-007 | A07 | JWT has no expiration | Medium | Medium | High | P2 |
| SEC-008 | A03 | Sales-report SQL injection | High | Medium | High construction / Medium impact | P1 |
| SEC-009 | A04 | Locally paid payment record lacks verification | High | Medium | High code / Medium downstream | P1 |
| SEC-010 | A05 | Debug and documented seed credentials by default | High | Medium | High code / Medium deployment | P1 |
| SEC-011 | A05 | Exception strings returned to clients | Medium | Medium | High code / Medium disclosure | P2 |
