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



## Launch configuration and operational checks

Copy `.env.example` to `.env` and configure the values in your hosting provider's
secret/environment settings. Never commit `.env` or paste live credentials into
source files.

For a production deployment:

- Set `ENVIRONMENT=production`, `DEBUG=false`, `COOKIE_SECURE=true`, and a unique
  `JWT_SECRET_KEY` of at least 32 characters.
- Set `FRONTEND_BASE_URL` to the deployed frontend origin and set
  `CORS_ORIGINS` to the exact allowed frontend origin(s), comma-separated.
- Set `PAYSTACK_CALLBACK_URL` to the deployed frontend's payment callback page.
  The backend passes this value to Paystack; it does not construct a production
  redirect from a localhost/default URL.
- Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
  `SMTP_FROM_EMAIL`, and `SMTP_USE_TLS` for password-reset and booking/request
  notification emails.
- Review `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, and
  `DB_POOL_RECYCLE_SECONDS` against the connection limit on your Neon plan.
- Run `alembic upgrade head` before deploying the new application version.

`GET /health` reports that the API process is alive. `GET /ready` executes a
database query and only reports ready when the configured database is reachable.
The versioned `GET /api/v1/health` endpoint remains available.

Booking creation, payment status, and the booking notification are committed in
the same database transaction for the payment-first checkout path. A booking is
created only after Paystack verification confirms the reference, amount, and
currency. Email notifications are queued after the transaction commits; an SMTP
failure does not roll back a paid booking.

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
- Distributed rate limiting and SMS delivery are not included. Monitor authentication, payment, and upload endpoints and add infrastructure-level rate limiting before scaling.
- Email delivery depends on a working SMTP provider and must be verified with real deployment credentials before launch.

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

Tutova collects lesson payments through Paystack. Tutor monthly fees and the
applicable tenure-based commission split are snapshotted into a monthly tutoring
arrangement. The learner's proposed lesson date, duration, and notes are stored
on the pending payment until the provider confirms the transaction; a booking
is not created before successful verification.

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

1. A parent or adult learner submits a tutoring request. For a direct request, the
   selected tutor accepts or declines it. For a general request, matching tutors
   can express interest and the learner selects one tutor.
2. Once the tutoring request is accepted and has an assigned tutor, the learner
   initializes checkout with
   `POST /api/v1/payments/requests/{request_id}/initialize`, sending the proposed
   booking schedule in the request body and an `Idempotency-Key` header.
3. The payment record stores the proposed schedule while `booking_id` remains
   `NULL`. No lesson booking is created at this stage.
4. The frontend redirects to the `checkout_url` returned by Paystack. Paystack
   returns to the configured `PAYSTACK_CALLBACK_URL`; the backend independently
   verifies the reference, amount, and currency. The Paystack webhook performs
   the same server-to-server verification.
5. Only after successful verification does the backend atomically mark the
   payment as paid, create the booking, and record the tutor's in-app notification.
   A failed, abandoned, or unverified payment does not create a booking.
6. The tutor reviews the paid booking using
   `POST /api/v1/session-bookings/{booking_id}/accept` or
   `POST /api/v1/session-bookings/{booking_id}/decline`.
7. Learners and tutors can view their transactions through
   `GET /api/v1/payments/mine`; a single transaction is available through
   `GET /api/v1/payments/{payment_id}`.

### Commission policy

Commission is based on completed calendar months since administrator approval and snapshotted when an arrangement or payment is created: 20% in the first month, 15% after one month and before three months, and 10% from the exact three-month approval anniversary. Parents/adult learners always pay a flat 5% of the agreed tutoring amount; the tutor contributes the remaining commission from agreed earnings. Historical transactions and existing arrangement snapshots are never repriced when a tutor crosses a tier.

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
