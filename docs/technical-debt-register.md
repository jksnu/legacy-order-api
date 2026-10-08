# Technical Debt Register

## Executive Summary

The application is a small Flask service with a single API blueprint, direct SQLAlchemy ORM access from route handlers and helpers, module-global database/app state, and six table models. It has no visible migration, background-worker, or payment-gateway layer. Startup creates tables and seeds development accounts. Behavior is straightforward to trace, but transport, authorization, business workflow, and persistence decisions are concentrated in `routes.py`.

The highest-priority debt is inconsistent object-level authorization: authenticated users can access or mutate other users' customer/order resources, and non-admin order creation can accept a client-selected customer ID. Four findings tie at the highest score (16/P0): TD-001, TD-002, TD-004, and TD-007. For a five-item summary, TD-003 is the next-ranked representative (12/P1); TD-005, TD-006, and TD-011 also tie at 12/P1. These cover unsafe report SQL, default secret/debug settings, payment-failure logging of submitted card data, and limited tests.

Most coupled components are `routes.py` (broad imports and orchestration), `models.py` (shared by nearly every runtime module), and `database.py` (global extension shared throughout). The biggest maintainability concern is the route module combining HTTP, authorization, validation, business workflows, and persistence. The biggest reliability concern is order creation's transaction boundary: a new order is flushed before item validation, but the route only rolls back recognized exceptions; other write paths commit locally and the global error handler does not explicitly roll back. The biggest testing concern is the five-test suite's lack of characterization for order creation, payments, reports, error paths, resource ownership, and most CRUD handlers.

## Scoring

Impact and likelihood use the requested 1–4 scales. Priority score is their product: 13–16 P0, 9–12 P1, 5–8 P2, 1–4 P3. Effort is a rough engineering estimate, not a measured metric. Confidence describes confidence that the finding exists from the inspected repository evidence, not certainty about its production exploitability. Cyclomatic complexity and runtime performance have not been measured.

## Findings

### TD-001

- **Title:** Order object endpoints lack ownership and role checks
- **Category:** Reliability / Authorization boundary / Architecture
- **Affected files:** [routes.py](../routes.py)
- **Evidence:** `get_order`, `update_order_status`, `delete_order`, `pay_order`, and `get_payment` use `login_required` (or no stronger per-object policy) and load by ID without checking the authenticated user's customer ownership. The source comment in `get_order` explicitly calls out missing ownership enforcement. `orders` does filter customer listing, but that filter is not reused by the other handlers.
- **Why it is technical debt:** Resource policy is inconsistent across endpoints and duplicated implicit assumptions are not centralized.
- **Impact:** 4 (Critical)
- **Likelihood:** 4 (Very Likely)
- **Priority score / priority:** 16 / P0
- **Remediation effort:** L
- **Confidence:** High

### TD-002

- **Title:** Order creation trusts client-selected customer ID
- **Category:** Reliability / Authorization boundary
- **Affected files:** [routes.py](../routes.py)
- **Evidence:** `add_order` accepts request `customer_id`; for non-admin callers it only looks up the caller's customer if that value is falsey. A truthy supplied ID is passed to `create_order` unchanged.
- **Why it is technical debt:** The route does not enforce that a customer-role user creates an order against their own customer record.
- **Impact:** 4 (Critical)
- **Likelihood:** 4 (Very Likely)
- **Priority score / priority:** 16 / P0
- **Remediation effort:** S
- **Confidence:** High

### TD-003

- **Title:** Sales report interpolates request values into SQL
- **Category:** Reliability / Data access
- **Affected files:** [reports.py](../reports.py)
- **Evidence:** `sales_report` concatenates `start` and `end` request arguments into SQL passed to `text()` and executes it.
- **Why it is technical debt:** User input is treated as SQL syntax rather than bound data, making report correctness and database safety depend on input contents.
- **Impact:** 4 (Critical)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 12 / P1
- **Remediation effort:** S
- **Confidence:** High

### TD-004

- **Title:** Product update is available to every authenticated role
- **Category:** Reliability / Authorization boundary
- **Affected files:** [routes.py](../routes.py)
- **Evidence:** `update_product` is decorated with `login_required`, not `admin_required`; it directly updates name, price, and stock. The code comment also identifies the price authorization issue.
- **Why it is technical debt:** Write policy differs from product creation, which is admin-only, and allows customer-role users to alter catalog fields.
- **Impact:** 4 (Critical)
- **Likelihood:** 4 (Very Likely)
- **Priority score / priority:** 16 / P0
- **Remediation effort:** S
- **Confidence:** High

### TD-005

- **Title:** Payment failure log includes card number input
- **Category:** Reliability / Logging and data handling
- **Affected files:** [utils.py](../utils.py), [routes.py](../routes.py)
- **Evidence:** `pay_order` passes `card_number` to `log_payment_failure`; the logger formats the complete value into a warning message. The source comment marks this as intentionally unsafe.
- **Why it is technical debt:** Sensitive payment input can be retained in logs, which may have different access and retention controls than payment processing.
- **Impact:** 4 (Critical)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 12 / P1
- **Remediation effort:** S
- **Confidence:** High

### TD-006

- **Title:** Development secret and debug-on defaults are embedded in configuration
- **Category:** Configuration / Reliability
- **Affected files:** [config.py](../config.py)
- **Evidence:** Missing `JWT_SECRET` falls back to a literal development string; missing `FLASK_DEBUG` evaluates to `true`. `app.py` uses the configured debug value when run directly.
- **Why it is technical debt:** Safe runtime behavior depends on operators overriding code defaults; a deployment with omitted variables silently uses development values.
- **Impact:** 4 (Critical)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 12 / P1
- **Remediation effort:** S
- **Confidence:** High

### TD-007

- **Title:** Customer resource access is not scoped to the caller
- **Category:** Reliability / Authorization boundary
- **Affected files:** [routes.py](../routes.py)
- **Evidence:** Customer list, detail, create, and update routes require only login. List returns all customers; detail/update load by ID. Delete is admin-only. No caller/customer association check appears in those handlers.
- **Why it is technical debt:** Access policy is role-only or absent for customer records despite a `Customer.user_id` association and customer-specific order listing behavior.
- **Impact:** 4 (Critical)
- **Likelihood:** 4 (Very Likely)
- **Priority score / priority:** 16 / P0
- **Remediation effort:** M
- **Confidence:** High

### TD-008

- **Title:** Route module combines transport, policy, workflow, and ORM persistence
- **Category:** Architecture / Maintainability
- **Affected files:** [routes.py](../routes.py)
- **Evidence:** The module declares all API handlers, parses request bodies, applies guards, performs ORM reads/writes, validates status/payment inputs, handles rollback, and invokes utilities. It imports all six models and most runtime helpers.
- **Why it is technical debt:** A change in HTTP shape, business policy, or persistence may affect the same large integration module; responsibilities are difficult to test independently.
- **Impact:** 3 (High)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 9 / P1
- **Remediation effort:** XL
- **Confidence:** High

### TD-009

- **Title:** Persistence transaction ownership is distributed and exception behavior differs
- **Category:** Reliability / Maintainability
- **Affected files:** [routes.py](../routes.py), [order_utils.py](../order_utils.py), [app.py](../app.py)
- **Evidence:** `create_order` commits internally; `add_order` catches exceptions and rolls back. Other handlers commit directly. The app-wide exception handler returns an error response but does not explicitly roll back the session. `register` flushes after creating a user and later commits the user/customer together, without a local exception/rollback block.
- **Why it is technical debt:** Callers do not own a consistent transaction boundary, and failure cleanup varies by endpoint. Exact session teardown behavior is delegated to Flask-SQLAlchemy and does not remove the code-level inconsistency.
- **Impact:** 3 (High)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 9 / P1
- **Remediation effort:** M
- **Confidence:** High

### TD-010

- **Title:** Catch-all handler exposes exception details and masks HTTP exception semantics
- **Category:** Reliability / Error handling
- **Affected files:** [app.py](../app.py)
- **Evidence:** `handle_error` catches `Exception` and responds with `str(error)` and the exception class name at status 500. There is no visible branch to preserve specific HTTP exception status codes in this handler.
- **Why it is technical debt:** Error responses expose internal exception details and can normalize otherwise meaningful framework exceptions to 500 depending on Flask dispatch behavior.
- **Impact:** 3 (High)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 9 / P1
- **Remediation effort:** S
- **Confidence:** Medium. The handler is explicit; exact handling of all HTTP exceptions depends on Flask's error-handler resolution.

### TD-011

- **Title:** Test suite covers only a small subset of API behavior
- **Category:** Testing / Maintainability
- **Affected files:** [tests/test_basic.py](../tests/test_basic.py)
- **Evidence:** The module contains five tests: login success, public product list, customer order-list success, admin product creation, and customer product-create denial. There are no tests in the repository for registration, customer CRUD, product update, order create/status/delete/detail ownership, payments, report query behavior, malformed input, or failure rollback.
- **Why it is technical debt:** Important business rules and error paths can change without a failing characterization test. Existing tests verify statuses/happy paths more than response/persistence invariants.
- **Impact:** 3 (High)
- **Likelihood:** 4 (Very Likely)
- **Priority score / priority:** 12 / P1
- **Remediation effort:** L
- **Confidence:** High

### TD-012

- **Title:** Financial values use binary floating-point columns and arithmetic
- **Category:** Reliability / Domain modeling
- **Affected files:** [models.py](../models.py), [order_utils.py](../order_utils.py)
- **Evidence:** `Product.price`, `Order.total`, `OrderItem.unit_price`, and `Payment.amount` are `db.Float`. Order calculations use floating-point multiplication and round only the final taxed total.
- **Why it is technical debt:** The representation does not explicitly encode decimal currency precision or a rounding policy for line values and payments.
- **Impact:** 3 (High)
- **Likelihood:** 2 (Possible)
- **Priority score / priority:** 6 / P2
- **Remediation effort:** L
- **Confidence:** High

### TD-013

- **Title:** Schema lifecycle is managed by create-all and seed-on-import rather than visible migrations
- **Category:** Architecture / Reliability
- **Affected files:** [app.py](../app.py), [models.py](../models.py)
- **Evidence:** `create_app` invokes `db.create_all()` and `seed_data()`; no migration tool or migration directory is present in the repository inventory. `app.py` also creates a global app during import.
- **Why it is technical debt:** Schema evolution and startup responsibilities are coupled; `create_all()` creates missing tables but is not a versioned migration history. Importing the module can trigger database work.
- **Impact:** 3 (High)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 9 / P1
- **Remediation effort:** L
- **Confidence:** High for repository contents and startup behavior; deployment may use external migration procedures not present here (Unknown).

### TD-014

- **Title:** Several helpers/configuration values are unused by repository call sites
- **Category:** Maintainability / Dead or suspicious code
- **Affected files:** [utils.py](../utils.py), [customer_utils.py](../customer_utils.py), [order_utils.py](../order_utils.py), [config.py](../config.py)
- **Evidence:** No in-repository call sites were found for `parse_date`, `check_stock`, `find_customer_by_email`, `calculate_order_total`, or `DEFAULT_PAGE_SIZE`. `calculate_order_total` duplicates the tax/subtotal calculation performed inside `create_order`.
- **Why it is technical debt:** Unused or overlapping entry points create uncertainty about the canonical implementation and increase maintenance surface. External imports are not knowable from this repository.
- **Impact:** 2 (Medium)
- **Likelihood:** 2 (Possible)
- **Priority score / priority:** 4 / P3
- **Remediation effort:** S
- **Confidence:** High for lack of in-repository call sites; external usage is Unknown.

### TD-015

- **Title:** Deprecated ORM and datetime APIs are used
- **Category:** Dependencies / Maintainability
- **Affected files:** [auth.py](../auth.py), [models.py](../models.py)
- **Evidence:** `current_user` uses `User.query.get(...)`; model timestamps use `datetime.utcnow`. The repository's test run under its configured Python environment emitted SQLAlchemy `Query.get()` legacy warnings and Python 3.13 `datetime.utcnow()` deprecation warnings.
- **Why it is technical debt:** These APIs produce runtime warnings and may require changes as dependency/runtime support evolves.
- **Impact:** 2 (Medium)
- **Likelihood:** 3 (Likely)
- **Priority score / priority:** 6 / P2
- **Remediation effort:** S
- **Confidence:** High

### TD-016

- **Title:** Declared requests dependency has no observed source use
- **Category:** Dependencies / Maintainability
- **Affected files:** [requirements.txt](../requirements.txt)
- **Evidence:** `requests==2.32.3` is listed, but no repository Python module imports `requests`; no outbound HTTP client usage is evident.
- **Why it is technical debt:** An apparently unnecessary direct dependency expands install/update surface. Whether an external execution tool relies on it is Unknown.
- **Impact:** 1 (Low)
- **Likelihood:** 2 (Possible)
- **Priority score / priority:** 2 / P3
- **Remediation effort:** S
- **Confidence:** High for no observed import; external/packaging use is Unknown.

## Additional Assessment Notes

- **Duplicated responsibilities:** `calculate_order_total` and the total calculation in `create_order` both compute subtotal plus tax; only the latter has an observed route caller.
- **Magic values:** Tax is centralized as `TAX_RATE`, but allowed order statuses are inline literals in `routes.py`; default payment method, transaction reference format, seed credentials/data, and report date bounds are literals in source.
- **Naming/pattern consistency:** CRUD endpoints vary in validation and guard strength; product creation uses `validate_product_payload`, while product update performs direct conversions. No separate request schema/validation layer is present.
- **Large functions/complexity:** `routes.py` is the largest observed responsibility cluster. Function sizes and cyclomatic complexity have not been measured; no numeric complexity claim is made.
- **Database constraints:** `User.email` is unique; foreign keys exist. No relationships, explicit cascade configuration, unique payment-per-order constraint, or customer email uniqueness are declared in `models.py`.
- **Background processing/integrations:** None evidenced. A payment record is created locally; no payment provider, task queue, or worker is called.
- **Logging:** No logging setup/structured logging configuration is visible; one warning call exists for failed card validation.
- **Actual test result:** `pytest -q` completed with 5 passed and 22 warnings in the configured workspace environment. Warnings included `Query.get()` and `datetime.utcnow()` deprecations. This is a baseline, not evidence of untested behavior being correct.
- **Metrics:** Cyclomatic complexity, coverage percentage, latency, throughput, and production failure rates have not been measured.

## Evidence and Traceability

- `routes.py`: `customers`, `customer`, `add_customer`, `update_customer`, `delete_customer`, `update_product`, `orders`, `get_order`, `add_order`, `update_order_status`, `delete_order`, `pay_order`, `get_payment`, `report_sales`.
- `reports.py`: `sales_report` SQL construction and execution.
- `utils.py`: `log_payment_failure`, product validation, date/stock helper functions.
- `auth.py`: token parsing/user lookup and authorization decorators.
- `order_utils.py`: `calculate_order_total`, `create_order`, stock decrement, commit behavior.
- `models.py`: declared columns, data types, foreign keys, defaults, and constraints.
- `config.py`: environment defaults and constants.
- `app.py`: startup, seeding, catch-all handler, module-level app.
- `tests/test_basic.py`: test fixture and five test cases.
- `requirements.txt`: declared versions; `README.md`: documented runtime/test command and intended training context; `pytest.ini`: test discovery setup.
- `git status --short --untracked-files=all` showed a pre-existing deletion of `seed_notes.md`; it was not read or changed.