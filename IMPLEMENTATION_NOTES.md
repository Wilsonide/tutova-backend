# Tutova password reset, daily progress log, and commission policy update

## Commission policy (current policy for newly created arrangements and payments)

The total Tutova commission is based on completed calendar months since the tutor approval date. The parent/adult learner always pays a flat 5% of the agreed tutoring amount. The tutor contributes the balance of the total commission from the tutor's agreed earnings.

- New tutor, first month: 20% total (15% tutor contribution + 5% parent fee).
- Relatively new tutor, after one month and before three months: 15% total (10% tutor contribution + 5% parent fee).
- Returning tutor, from completion of three months: 10% total (5% tutor contribution + 5% parent fee).

The three-month tier starts on the exact three-month anniversary of administrator approval. Each new monthly arrangement stores an immutable monthly schedule, including the total commission rate, fixed 5% parent fee rate, and monetary split. Existing arrangements, payments, and historical snapshots are not repriced or rewritten.

## Password reset

- Added `POST /api/v1/auth/forgot-password` and `POST /api/v1/auth/reset-password`.
- Added `/forgot-password` and `/reset-password?token=...` frontend pages.
- Reset tokens are cryptographically random, stored as SHA-256 hashes, expire after 30 minutes by default, and can only be used once.
- Resetting a password revokes all refresh sessions for that user.
- The forgot-password endpoint returns a generic response and applies a 60-second account cooldown.
- SMTP and `FRONTEND_BASE_URL` must be configured for email delivery.

## Daily progress log

- Added a chat-style progress room for each accepted tutoring request.
- Tutors and parents/adult learners can post daily updates, milestones, questions, and concerns.
- Entries use the Africa/Lagos calendar date and are ordered chronologically.
- Admins can supervise, review, flag, annotate, and resolve entries.
- The room refreshes using regular HTTP polling; no WebSockets are required.
- Existing per-lesson progress reports are retained for compatibility.

## Database migration

The password reset and progress log migration remains `d8f4a1c9b2e7` (parent `c6f2a9d1e840`). This commission policy update changes business logic and JSON snapshots only; it does not require a new database migration.

Run from the backend project directory:

```powershell
uv run alembic upgrade head
```
