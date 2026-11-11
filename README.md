# Tutova Backend

A feature-first FastAPI modular monolith for a safeguarding-first tutoring marketplace. This repository is a runnable foundation, not a claim that every workflow in the full specification has been completed.

## Included in this delivery

- FastAPI application, `/api/v1` router composition, health/readiness endpoints.
- Async SQLAlchemy 2.x database session setup and Alembic model registration.
- Parent/tutor registration, login, logout, access JWTs, HTTP-only refresh cookies, refresh-token rotation/revocation, Argon2 password hashing.
- User roles and account status, role dependencies, controlled admin bootstrap command.
- Tutor application persistence and initial submission/list/review workflow with admin authorization.
- Initial Alembic migration, tests for security primitives and pricing-independent auth invariants, Docker and environment template.

## Quick start

1. Install Python 3.11+ and PostgreSQL (or create a Neon database).
2. Create a virtual environment and install: `pip install -e '.[test]'`.
3. Copy `.env.example` to `.env` and set `DATABASE_URL` and a strong `JWT_SECRET_KEY`. Use `postgresql+asyncpg://...` for async SQLAlchemy.
4. Run migrations: `alembic upgrade head`.
5. Start: `uvicorn app.main:app --reload`.
6. Visit `/docs`, `/health`, and `/ready`.

## Create the first administrator

Set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` in the environment, then run `python -m scripts.bootstrap_admin`. This command creates an ADMIN only if no account with that email exists. It does not expose a public admin registration route. Use a one-time secret and rotate credentials after initial provisioning.

## Tests

Run `pytest`. Tests that need PostgreSQL should use an isolated test database; no live payment credentials are required.

## Architecture

`app/core` contains shared security/configuration/HTTP error handling. `app/db` owns the SQLAlchemy base and session. `app/api` composes versioned routers and dependencies. Every business feature lives under `app/domain/<feature>` and owns its own models, repositories, services, schemas, and router.

## Security notes

- Access tokens are short-lived; refresh tokens are opaque random values stored only as SHA-256 hashes in the database and rotated on use.
- Refresh cookies are HTTP-only. Set `COOKIE_SECURE=true` in production and serve only over HTTPS.
- Configure exact CORS origins. Do not log secrets or provider payloads.
- This foundation does not yet implement production-grade distributed rate limiting, email/SMS delivery, payment-provider integrations, or the complete safeguarding and accounting workflows. Add those before public launch.

## Outstanding business decisions

Confirm launch location, email/SMS verification provider, password-reset delivery, tutor verification policy, NDA text/version ownership, video duration/storage provider, meet-and-greet fee, cancellation/refund/partial-hour rules, payment provider, payout maker-checker policy, earnings eligibility, and final Nigerian accounting/tax treatment with qualified advisers.

## Tutor marketplace additions

Tutors are not limited to school subjects. Offerings support `SCHOOL_SUBJECT`, `CODING`, `PROFESSIONAL`, `LANGUAGE`, `CREATIVE_SKILL`, and `OTHER`; titles and descriptions allow tutors to define the specific course, such as Python, web development, data analysis, project management, exam preparation, or a creative skill.

Tutor self-service endpoints:

- `PUT /api/v1/tutors/me/profile` — create/update public-facing biography, experience, work modes (`ONLINE`, `IN_PERSON`, `HYBRID`), service area, timezone, learner availability preference, and payout-method preference.
- `GET /api/v1/tutors/me/profile`
- `POST /api/v1/tutors/me/offerings`, `GET /api/v1/tutors/me/offerings`, `DELETE /api/v1/tutors/me/offerings/{offering_id}`
- `POST /api/v1/tutors/me/availability`, `GET /api/v1/tutors/me/availability`, `DELETE /api/v1/tutors/me/availability/{slot_id}`. Days use Monday=0 through Sunday=6, with explicit timezone and non-overlapping time windows.
- `POST /api/v1/tutors/me/offerings/{offering_id}/pricing` and `GET /api/v1/tutors/me/pricing`.
- `PATCH /api/v1/tutors/admin/pricing/{pricing_id}/review?approved=true|false` — admin-only pricing review.
- `GET /api/v1/tutors/discover?category=CODING&mode=ONLINE` — public discovery query, currently fail-closed by the publication flag.

Pricing is tutor-proposed and administrator-approved. `HOURLY` and `CONTRACT` are supported; contract pricing requires a scope description. Monetary values are integer kobo (`amount_minor`) and currently use NGN. Price versions are retained; a prior active version remains active until a replacement proposal is approved.

`payout_method_preference` records the tutor's preference only; it is not a verified payout destination and does not initiate transfers. Actual bank-account verification and payout execution belong to the later payout domain.

### Publication safety gate

Public discovery deliberately remains closed by default. Approval of a tutor application and a price alone must not publish a tutor: the required verification checks, current NDA acceptance, approved introduction video, and pricing approval must all be implemented and evaluated before a secure publication workflow is enabled. Do not manually set `tutor_profiles.is_public` in production to bypass those gates.

## Running with uv

```powershell
uv sync --extra test
Copy-Item .env.example .env
# Configure DATABASE_URL and a unique JWT_SECRET_KEY in .env
uv run alembic upgrade head
uv run pytest -v
uv run uvicorn app.main:app --reload
```

## Payments (Paystack)

Tutova collects lesson payments through Paystack. A tutor sets `hourly_rate` (NGN) on their tutor profile. When the tutor proposes a booking, the API snapshots that rate and calculates the gross lesson charge from `duration_minutes`; later tutor rate changes do not alter an existing booking price.

Configure these environment variables before enabling checkout:

```env
PAYMENT_PROVIDER=PAYSTACK
PAYSTACK_SECRET_KEY=sk_test_or_live_your_key
PAYSTACK_BASE_URL=https://api.paystack.co
PAYSTACK_CALLBACK_URL=https://your-frontend.example/payment/callback
PAYSTACK_CHANNELS=card,bank_transfer,ussd
PAYSTACK_TIMEOUT_SECONDS=15
```

Configure the Paystack webhook URL as `https://your-api.example/api/v1/payments/webhook`. The webhook is authenticated with Paystack's `x-paystack-signature` header and successful charges are independently verified against Paystack before being marked paid.

### Payment flow

1. Tutor creates a tutor profile or updates it with `hourly_rate` in NGN (`PATCH /api/v1/tutors/profile`).
2. Tutor proposes a lesson using `POST /api/v1/session-bookings/requests/{request_id}`. The response includes `hourly_rate`, `gross_amount_minor` (kobo), and `currency`.
3. Parent/adult learner confirms the booking using `POST /api/v1/session-bookings/{booking_id}/confirm`.
4. Requester initializes checkout using `POST /api/v1/payments/bookings/{booking_id}/initialize` with an `Idempotency-Key` header. The response includes the Paystack `checkout_url`.
5. Frontend redirects to `checkout_url`. After payment, the frontend can verify using `POST /api/v1/payments/reference/{reference}/verify`; Paystack also notifies the webhook endpoint.
6. Requester and tutor can view relevant transactions through `GET /api/v1/payments/mine`; a single transaction is available through `GET /api/v1/payments/{payment_id}`.

### Commission policy

Commission is snapshotted at payment initialization and calculated from the tutor's previously completed, learner-acknowledged lesson hours: 25% at zero completed hours, 20% above zero through exactly 50 hours, and 15% above 50 hours. The remaining amount is recorded as tutor earnings. Historical transactions are never repriced when a tutor crosses a tier.

All Paystack amounts are integer kobo. The payment API only permits payment for confirmed bookings, checks the payer against the booking requester, and verifies provider reference, amount, and currency before recording a successful payment.

Apply the database migration with:

```bash
alembic upgrade head
```

## Payment operations: tutor payouts and refunds

The payment module includes Paystack-backed tutor bank destinations, tutor payout requests, admin-controlled transfer processing, transfer verification, partial/full refunds, refund verification, and Paystack transfer/refund webhook handling.

### Tutor payout setup and lifecycle

1. A tutor saves a Nigerian bank destination with `PUT /api/v1/payments/payout-destination` (`account_name`, `account_number`, `bank_code`). Tutova sends the bank details to Paystack to create a transfer recipient. Tutova stores only Paystack's recipient code, bank/account display name, and last four account digits; it does not store the full account number.
2. A tutor requests payout for an individual paid lesson using `POST /api/v1/payments/payouts/request/{payment_id}`. The lesson must be completed and acknowledged by the learner, and no refund can be pending for it.
3. Admins review `GET /api/v1/payments/admin/payouts`, then initiate `POST /api/v1/payments/admin/payouts/{payout_id}/process`.
4. Paystack may queue transfers asynchronously. Tutova records `PROCESSING` and reconciles using `POST /api/v1/payments/admin/payouts/{payout_id}/verify` or the `transfer.success`, `transfer.failed`, and `transfer.reversed` webhook events. If Paystack requires transfer OTP approval, an admin finalizes it using `POST /api/v1/payments/admin/payouts/{payout_id}/finalize` with the OTP. A failed/reversed transfer can be re-queued by an admin using `POST /api/v1/payments/admin/payouts/{payout_id}/retry`.
5. Tutors see eligible lesson earnings at `GET /api/v1/payments/payouts/eligible` and payout history at `GET /api/v1/payments/payouts/mine`.

### Refund lifecycle

Only admins can initiate a refund using `POST /api/v1/payments/admin/{payment_id}/refund` with `amount_minor` (kobo) and `reason`. Partial and full refunds are supported. Refunds are blocked once a tutor payout has been requested, is processing, or has been paid, because clawing back an already transferred tutor earning requires a separate debt/recovery workflow. Pending refunds reserve the transaction against another refund or payout. Reconcile refunds using `POST /api/v1/payments/admin/refunds/{refund_id}/verify` and the Paystack refund webhook events. Admins can inspect refund records at `GET /api/v1/payments/admin/refunds`.

### Operational requirements

- Configure `PAYMENT_PROVIDER=PAYSTACK` and a live/test `PAYSTACK_SECRET_KEY` as appropriate.
- Enable Transfers on the Paystack integration and ensure the business account is eligible and funded for transfers. Depending on Paystack's transfer approval settings, transfers may require dashboard OTP approval.
- Configure the Paystack webhook URL as `/api/v1/payments/webhook` and use the same secret key for signature verification.
- Payouts are one per paid lesson/payment in this implementation. Platform commission and tutor earning snapshots on the original payment are immutable; refund rows separately record the amount allocated to the tutor and platform.
- Paystack transaction processing fees are not assumed to be refundable. Check Paystack settlement/balance before initiating live refunds or transfers.
