# Tutor onboarding follow-up implementation

## Frontend changes
- Education certificate and certification uploads use XMLHttpRequest upload progress, show percentages, completion, and retryable errors.
- Tutor NDA is loaded from the backend, displayed as a complete scrollable document, and requires an explicit agreement action.
- Onboarding form state is automatically saved to the authenticated tutor's server-side draft and restored on the next login.
- Admin verification view can load full referee form responses, view identity/education/certification documents through expiring links, play the tutor introduction video, and inspect the NDA snapshot and acceptance metadata.

## Backend changes
- `GET /api/v1/verification/tutor/nda`: returns the current NDA version and text.
- `POST /api/v1/verification/tutor/nda/accept`: records explicit acceptance, immutable NDA text snapshot, acceptance timestamp, client IP and user-agent.
- Verification submission requires acceptance of the current NDA version.
- `GET|PUT|DELETE /api/v1/tutors/profile/draft`: retrieve, save and clear the tutor's server-side onboarding draft.
- `GET /api/v1/tutors/profile/admin/verification/{verification_id}/background`: admin-only education, certification and work-history details.
- Existing admin referee endpoint returns structured referee form answers, declaration/consent details, submission timestamp, IP and safeguarding flags.
- Admin verification responses include the introduction video URL and NDA acceptance snapshot.

## Migration
Run:

```powershell
uv run alembic upgrade head
```

The new revision is `f2a6c9d1e840` and follows `ed6a1b2c3d40`.

## NDA review
The included agreement is a working product draft for Tutova's workflow. Have a qualified Nigerian legal practitioner review and approve the wording before production use. Changing the text should also involve changing `CURRENT_NDA_VERSION` so that existing acceptance records remain tied to the exact version accepted.

## Validation performed
- Python AST/compile checks passed for application modules and the new migration.
- TypeScript transpilation/syntax checks passed for the modified onboarding page, admin console and API utility.
- A full Next.js typecheck/build and backend runtime/DB integration test could not be completed in this environment because frontend dependencies were not installed and the backend environment lacks `asyncpg`.
