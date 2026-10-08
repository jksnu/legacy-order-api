# Remediation Agent Skill

## Purpose & Scope

Use these rules when implementing an approved remediation in `legacy-order-api`. They are reusable guardrails for a future coding agent, not an authorization to remediate during analysis or planning phases. Work only on the requested finding(s) and the smallest relevant application/test surface. Preserve existing behavior unless the approved security, business, or architecture decision explicitly requires a contract change.

The repository is a Flask API with route handlers in `routes.py`, JWT helpers in `auth.py`, SQLAlchemy models in `models.py`, shared session setup in `database.py`, business helpers including `order_utils.py`, and pytest coverage in `tests/test_basic.py`. Payment behavior is local-only in the observed code; no provider integration is established. Treat those as current facts, not as desired architecture.

## Core Remediation Rules

**R1. Evidence before edits.** Trace the finding to the live route/function, relevant model/config/helper, all callers, response contract, existing tests, and any adjacent behavior. State the observed failing behavior and one regression check before editing. Do not rely on prior findings without verifying the current source.

**R2. Minimal safe change.** Correct the specific verified weakness with the smallest coherent change. Avoid unrelated cleanup, renaming, broad abstraction work, or opportunistic refactoring. Preserve legitimate positive paths and existing API shape unless the approved finding requires a change.

**R3. One change slice at a time.** Make a focused edit, run its narrowest useful regression test immediately, and repair only that slice if it fails. Do not expand into adjacent behavior before the first check resolves the hypothesis.

**R4. Respect ownership boundaries.** Enforce authorization at the resource/action boundary, not merely at route entry. For any protected customer/order/payment/product operation, resolve the resource and verify either the authenticated user's ownership or an explicitly authorized role. Apply the same policy to list, detail, create, update, delete, status, and nested-resource routes as applicable.

**R5. Preserve observable contracts.** Record current methods, paths, status codes, response fields, and successful flows before changing them. Alter an API contract only when required by the approved security/business change; document the change and test both the new behavior and intended compatibility.

## Authentication & Authorization

**R6. Never trust caller-selected ownership.** A non-admin caller's owner/customer identity must come from authenticated server-side identity and its verified association. Do not accept `customer_id`, `user_id`, role, or similar request/token claims as proof of permission. If administrators may act for another customer, encode that exception as an explicit role policy and test both sides.

**R7. Enforce role boundaries consistently.** Compare each mutation against the approved role/action policy. A guard on create does not imply the update path is protected. Keep authorization checks close to the operation or use an established shared policy helper; do not leave alternate endpoints as bypasses.

**R8. Secure JWT lifecycle and fail closed.** Require a high-entropy secret from protected runtime configuration; do not ship or silently fall back to a known signing key. Include and validate a finite expiration and any approved issuer/audience constraints. Invalid, expired, malformed, or unverifiable tokens must not identify a user. Do not authorize from an unverified claim. Never log tokens or secrets.

## Input/SQL & Sensitive Data

**R9. Treat all inputs as untrusted.** Validate JSON shape, type, range, length, enum values, and required fields at the API boundary. Convert malformed input to a stable client error without uncaught conversion/index errors. Avoid duplicating inconsistent validation between create and update flows.

**R10. Keep SQL structure static.** Never concatenate request input into SQL, even after superficial validation. Use SQLAlchemy bound parameters for raw SQL values and ORM parameterization for filters; parse and validate semantic types such as dates separately. Regression-test malformed and injection-shaped values without relying on one database's permissive parsing.

**R11. Minimize sensitive-data exposure.** Never log passwords, password hashes, bearer tokens, JWT secrets, card/payment account data, or raw authentication headers. Log only an approved event, safe identifiers, and a fixed reason; redact untrusted data and avoid logging entire request bodies. Do not add sensitive fields to API serializers or error messages.

## Configuration & Error Handling

**R12. Fail closed on production configuration.** Do not introduce known production secrets, default credentials, or debug mode. Make unsafe development settings explicit and isolated from production startup. Do not assume environment overrides are deployed; validate required values at startup without printing them.

**R13. Separate client errors from diagnostics.** Return stable, non-sensitive client responses with appropriate HTTP status. Keep stack traces and database/provider details in controlled server diagnostics, with secret redaction and a correlation ID where appropriate. Do not convert authorization failures or expected HTTP errors into generic 500 responses.

## Database & API Compatibility

**R14. Preserve transaction atomicity.** Identify the full unit of work and ensure related writes either all commit or all roll back. Avoid helper-level partial commits that prevent the caller from maintaining atomicity. Do not introduce schema changes, migrations, or data backfills without explicit architectural approval and a rollback/compatibility plan.

**R15. Do not invent payment semantics.** Client-submitted amount, method, card text, or a locally generated transaction reference is not proof of payment. Do not mark payment successful without an established trusted verification source. No external payment provider is evidenced in the current repository: stop and ask before adding one, changing payment states, or assuming settlement/fulfillment rules.

## Testing & Validation

**R16. Prove denial and preservation.** Every security fix needs a regression test that demonstrates the previously unauthorized/unsafe request is denied or safely handled, plus a legitimate positive-path test. Cover each affected endpoint/action rather than testing only a shared decorator. Assert relevant persistence state and response contract, not only status code. Run focused tests first, then the full suite when practical; report any unrun or failing validation.

**R17. Keep traceability explicit.** Link the code change and each new/updated regression test to the original SEC or TD finding. Update remediation notes with the finding ID, affected behavior, test names, and any intentional API/schema change. Do not silently broaden scope beyond mapped findings.

## Dependency Rules

**R18. Evidence before dependency changes.** Do not claim a CVE from version age, a deprecation warning, or an unverified scanner result. Do not upgrade, add, or remove dependencies without a current authoritative advisory/effect analysis, compatibility rationale, and explicit approval. Prefer a narrowly scoped upgrade and run the relevant test suite when justified.

## Stop-and-Ask Conditions

Stop implementation and ask the repository owner for a decision when any of the following is unclear or required:

- Which customer/account owns a resource, whether administrators may act across owners, or whether one user may have multiple customer records.
- Which status transitions, deletion rules, or payment authorization/settlement semantics are valid.
- Whether a payment provider exists outside this repository, which provider is approved, or what verified callback/transaction evidence is trusted.
- Whether a fix requires changing endpoint methods/paths, response fields/statuses, token compatibility, or client-visible behavior.
- Whether a schema change, migration, data repair, or cascade policy is required.
- Which production secret manager, debug policy, deployment boundary, TLS termination, rate limiter, or logging/monitoring platform is authoritative.
- A remediation requires adding a dependency, external service, new privilege, or cross-cutting redesign not approved by the finding scope.
- Existing tests or source disagree with the finding and the intended behavior cannot be established from code or approved requirements.

Do not guess at a business rule to make a test pass. Record the open decision and the safe facts already established.

## Forbidden Behaviors

- Do not treat a prior architecture/security report as proof; re-check the current code and callers.
- Do not fix unrelated issues, reformat whole modules, rename public symbols, or refactor while implementing a narrow remediation.
- Do not trust client ownership IDs, caller-supplied roles, payment amounts, card text, or transaction references as authorization/verification.
- Do not concatenate untrusted input into SQL or log secrets/sensitive values.
- Do not add known credentials, production secrets, debug mode, payment providers, or schema changes without approval.
- Do not suppress, weaken, or delete an existing test to make the remediation pass.
- Do not claim exploitability, provider behavior, dependency CVEs, or deployment controls that evidence does not establish.
- Do not commit or alter files outside the explicitly approved implementation/test scope.

## Traceability Matrix

| Finding | Remediation rule(s) | Regression/validation expected |
|---|---|---|
| SEC-001 | R1, R2, R4, R6, R16, R17 | Customer cannot list/read/update another customer's data; authorized owner/admin positive path remains supported. |
| SEC-002 | R1, R2, R4, R6, R11, R16, R17 | Cross-owner order and payment reads are denied; owner/admin responses preserve approved fields. |
| SEC-003 | R1, R2, R4, R6, R7, R14, R15, R16, R17 | Non-admin cannot choose another `customer_id` or mutate another order; valid owner/admin order flows retain intended atomic behavior. Payment state tests must follow approved semantics. |
| SEC-004 | R1, R2, R7, R16, R17 | Customer product update denied; authorized administrator update remains functional. |
| SEC-005 | R1, R2, R11, R16, R17 | Payment failure logs contain no submitted card-like input or other sensitive value; normal validation response remains compatible. |
| SEC-006 | R1, R8, R12, R16, R17 | Missing/weak secret configuration fails closed; tokens signed under approved configuration validate, and invalid signatures fail authentication. |
| SEC-007 | R1, R8, R16, R17 | Expired token is rejected; valid unexpired token behavior and protected positive paths remain supported. |
| SEC-008 | R1, R2, R9, R10, R16, R17 | Bound date parameters preserve valid report behavior; malformed/injection-shaped input cannot alter SQL structure. Admin guard remains enforced. |
| SEC-009 | R1, R2, R14, R15, R16, R17 | Client-only values cannot establish paid status; verified payment success/failure paths follow approved provider/business semantics. Stop for approval if those semantics are not documented. |
| SEC-010 | R1, R2, R12, R16, R17 | Production startup does not enable debug or create reusable known credentials; isolated development/test seed behavior remains only if explicitly required. |
| SEC-011 | R1, R2, R11, R12, R13, R16, R17 | Client sees stable safe error response; controlled server diagnostics preserve useful correlation without leaking exception/DB secrets. |
