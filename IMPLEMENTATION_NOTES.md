# Tutova workflow implementation notes

## Commission policy

Tutor tenure starts at `TutorVerification.approved_at`, set when an administrator approves the tutor. Existing approved tutors are backfilled from `reviewed_at` where available.

Monthly commission snapshots use these total platform rates, split equally between tutor and learner:

- First month after approval: 25% total (12.5% tutor deduction + 12.5% learner fee).
- From one month until before three months: 20% total (10% + 10%).
- From completion of three months onward: 15% total (7.5% + 7.5%).

The monthly snapshots are retained on the arrangement/payment records so later tenure changes do not rewrite prior periods.

## Request and booking paths

### Direct tutor request

1. Learner selects a tutor and a subject from that tutor's taught subjects.
2. The request is created and admin is notified. The direct request is not placed in the generic matching queue.
3. Learner proposes the exact lesson time/duration and creates the booking.
4. Learner pays through Paystack while the booking is awaiting tutor confirmation.
5. Only after the verified payment is marked paid is the selected tutor notified to accept or decline the exact booking.
6. Tutor acceptance creates the agreement draft for tutor review; learner approval signs it and confirms the booking.

The profile request form still captures the initial preferred schedule as free text. The structured date/time and duration are collected in the subsequent booking step, and payment is collected immediately after that structured booking is created.

### Generic request

1. Learner submits a generic request.
2. Matching tutors may express interest; the request remains open while the learner reviews responses.
3. Learner selects one accepting tutor.
4. The selected tutor is assigned; other interested tutors are notified that the opportunity has been taken.
5. Learner creates the dated booking and pays.
6. Verified payment notifies the selected tutor and admin; the tutor can then accept/decline the exact booking.
7. Tutor acceptance creates the agreement draft; tutor review and learner approval complete the agreement.

## Agreements

New agreements snapshot subject, schedule, duration, venue/meeting link, booking amount, monthly commission breakdown and per-month commission schedule. Tutor can accept or propose a revised date/time/duration/venue/meeting link. The learner must approve the reviewed terms. A booking is not confirmed until the learner accepts the agreement.

If the learner declines after paying, the booking is cancelled and admins are notified to review the payment/refund. No automatic refund is issued.

## Progress reports and disputes

New bookings require one tutor report and one learner/parent report after the tutor marks a lesson completed. The learner cannot acknowledge completion until both reports exist. Reports are visible to the participants and administrators. Reporting an issue places the booking into `DISPUTED` and notifies admins.

Admin may return a reviewed dispute to learner acknowledgement or cancel the booking. Admin review does not impersonate the learner: the learner must still acknowledge completion manually. Unresolved disputes and unacknowledged lessons remain ineligible for payout.

Existing bookings are backfilled with `progress_reports_required = false` to preserve their previous acknowledgement flow.

## Admin monthly payouts

`POST /api/v1/payments/admin/payouts/prepare-month?period_start=YYYY-MM-DD` accepts any date in the target calendar month. It prepares admin-reviewable payout records for eligible contract-month windows. It does not transfer money automatically. Admins continue through the existing Paystack process/verification/OTP finalisation workflow.

Eligibility remains subject to month-end, all lessons in that contract month being completed and learner-acknowledged, and no unresolved dispute/admin review.

## Important API additions

- `POST /api/v1/tutoring-requests/mine/{request_id}/select-tutor/{tutor_profile_id}`
- `GET /api/v1/tutoring-requests/admin`
- `GET /api/v1/session-bookings/admin`
- `POST /api/v1/session-bookings/admin/{booking_id}/resolve-dispute`
- `GET /api/v1/payments/admin`
- `POST /api/v1/payments/admin/payouts/prepare-month`
- `GET /api/v1/agreements/mine`
- `POST /api/v1/agreements/{agreement_id}/tutor-accept`
- `POST /api/v1/agreements/{agreement_id}/tutor-request-changes`
- `POST /api/v1/agreements/{agreement_id}/learner-decision`
- `POST /api/v1/progress-reports/bookings/{booking_id}`
- `GET /api/v1/progress-reports/bookings/{booking_id}`
- `GET /api/v1/progress-reports/admin`
- `PATCH /api/v1/progress-reports/admin/{report_id}/review`

## Apply migrations

Back up the database, then run:

```powershell
uv run alembic upgrade head
```

The latest migration head is `f6b2c8d4a910`.
