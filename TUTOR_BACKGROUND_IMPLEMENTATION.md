# Tutor education and professional background

## Added API

All endpoints are under the existing `/api/v1` prefix.

- `GET /tutors/profile/background` — returns the authenticated tutor's education, certifications and work history.
- `PUT /tutors/profile/background` — atomically replaces the three background collections for the authenticated tutor.
- `GET /tutors/profile/institutions?q=...&country_code=NG` — searches approved institution records.
- `POST /tutors/profile/institutions/suggest` — submits an institution suggestion for admin review.
- `POST /tutors/profile/background/documents` — uploads a PDF/JPEG/PNG (10 MB maximum) to an authenticated Cloudinary asset and returns its `public_id` and filename. The tutor record stores the asset identifier, not a public delivery URL.
- `GET /tutors/profile/admin/institutions/suggestions` — lists pending institution suggestions for admins.
- `PATCH /tutors/profile/admin/institutions/{institution_id}` — approves or rejects a pending suggestion.

## Data and behavior

- One tutor can have multiple education records, certifications and work-history records.
- Education records include institution, country, course, specialty, programme/qualification type, grade, dates, current-enrolment flag and required supporting document in the onboarding UI.
- Certification and work-history entries are optional. Certification documents are optional.
- Institution suggestions are stored as `PENDING`; only approved institutions appear in the search dropdown. The typed institution name can still be saved against the tutor's education record while the suggestion awaits review.
- Work-history and education dates are validated so an end date cannot precede a start date. Ongoing records must not have an end date.
- The existing profile, identity verification, introduction-video and referee endpoints are unchanged.

## Migration

A new merge migration `ed6a1b2c3d40` joins the two existing Alembic heads in this archive and creates the four new tables. Apply it with:

```bash
uv run alembic upgrade head
```

Cloudinary must be configured using the existing backend environment variables. Background documents are uploaded with Cloudinary's `authenticated` asset type. The API returns only the asset public ID and format; it does not expose public document URLs. Admins can request a short-lived authenticated download URL with `GET /tutors/profile/admin/background-documents/{education|certification}/{record_id}`.
