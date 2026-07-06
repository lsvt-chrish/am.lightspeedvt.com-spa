# Check Users in Bulk

## Overview

The **Check Users** feature lets an authenticated user upload a spreadsheet (CSV or XLSX), pick one column as the lookup key, and get back two lists: rows whose users **exist** in LightSpeed VT, and rows whose users are **missing**. Both lists are downloadable as CSV.

Typical use cases:

- Validating an HR export against an existing LSVT system before a bulk enrollment.
- Auditing whether a partner-supplied list of learners was ever provisioned.

Authentication uses the app's session-based API credentials (same pattern as the other User Training Data features).

---

## User Flow

### Entry and Authentication

- **URL:** `/user-training-data/check-users` (Vue Router).
- **Entry point:** the **User Training Data** choice page ([frontend/src/views/CertificationsChoicePage.vue](frontend/src/views/CertificationsChoicePage.vue)) shows a **Check users in bulk** card alongside the existing tools. If `has_credentials` is `false`, the choice page directs the user to the Credentials drawer first.

### Steps

1. User selects a CSV or XLSX file. The browser immediately POSTs it to `/api/user-check/preview` (multipart) which parses the headers only and returns `{ format, headers, row_count }`.
2. A configuration panel appears. The user picks:
   - **Lookup column** &mdash; a dropdown populated from the file's actual headers (the page pre-selects a column named `email`, `username`, or `user id` if present).
   - **Lookup key type** &mdash; radio: `Email`, `Username`, or `User ID`.
3. User clicks **Check users**. The frontend POSTs the same `File` object again to `/api/user-check/check` (multipart, with `lookup_column` and `lookup_key_type` form fields).
4. The backend fetches every user in the LSVT system via paginated `list_users`, builds an index keyed by the chosen field, and splits the upload into two buckets:
   - `exists` &mdash; every original column, plus `matched_userId`, `matched_username`, `matched_email` from LSVT.
   - `missing` &mdash; every original column, plus a `reason` (`not found in system` or `lookup value empty`).
5. The UI shows a summary tiles panel (Total / Exists / Missing / Blank lookup), tabs for each bucket, and a preview of the first 50 rows.
6. The user clicks **Download exists.csv** or **Download missing.csv** to get the full lists.

Downloads are always CSV, regardless of the source format.

---

## API Integration

### Endpoints Used

| Purpose | Method / Endpoint | Notes |
|---------|-------------------|-------|
| List all users (system-wide) | `GET /users` | Paginated via `list_users` in [backend/app/lightspeed_api.py](backend/app/lightspeed_api.py). 200 rows per page, 200 ms pacing. |

### Matching Rules

- `email` and `username` &mdash; case-insensitive; the row value and index key are both `.strip().lower()`.
- `userId` &mdash; coerced through `int(float(...))`, so `"12345"`, `"12345.0"`, `12345`, and `12345.0` all resolve to the same key.

---

## Backend Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/user-check/preview` | `POST` (multipart) | Parses just the headers of the uploaded file. Returns `{ format, headers, row_count }`. Requires session credentials. |
| `/api/user-check/check` | `POST` (multipart) | Full split against LSVT. Multipart fields: `file`, `lookup_column`, `lookup_key_type` (`email` / `username` / `userId`). Returns the summary plus both bucket lists. Requires session credentials. |

Both routes:

- Require valid session credentials; return **401** otherwise.
- Are rate limited to **10 requests per minute per client IP** (custom in-memory limiter, mirrors [backend/app/api/training_export.py](backend/app/api/training_export.py)).
- Enforce a **20,000-row** and **20 MB** cap on uploads (returns **413** when exceeded).

Format detection: MIME type first (`text/csv` vs `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), with `.csv` / `.xlsx` filename fallback. Anything else is rejected with **415**.

---

## Frontend Routes and Views

| Vue route | View | Description |
|-----------|------|-------------|
| `/user-training-data/check-users` | [frontend/src/views/CheckUsersPage.vue](frontend/src/views/CheckUsersPage.vue) | Upload, configure, results table, per-bucket CSV download. |

Entry point: a card titled **Check users in bulk** on [frontend/src/views/CertificationsChoicePage.vue](frontend/src/views/CertificationsChoicePage.vue).

---

## Dependencies

- Backend: `python-multipart` (FastAPI needs it to accept `UploadFile`) and `openpyxl` (XLSX parsing). Both added to [backend/pyproject.toml](backend/pyproject.toml). **Rebuild the backend image** (`make up-build` or `docker compose build backend`) after pulling &mdash; the dev bind-mount doesn't cover Python dependencies.
- Frontend: none. XLSX parsing lives entirely on the backend; downloads are generated client-side with a small hand-rolled CSV writer inside the view.

---

## Known Limitations

- **`list_users` completeness.** If LSVT's `/users` endpoint doesn't return every user in the system for a given account, some genuine users will show as "missing". The training-export feature has a fallback that derives users from certification reports; if you see a known user in the missing bucket, we can port that fallback here.
- **XLSX cell coercion.** `openpyxl` returns typed values (numbers, dates). Cells are stringified: integers stay integer-looking (`123`), floats keep their decimal (`4.5`), and dates are ISO 8601. Excel cells with formatting like leading-zero IDs (`00042`) become `42` because openpyxl reads the underlying number &mdash; store such IDs as text in the source file.
- **CSV encoding.** UTF-8 (with BOM) is expected. Latin-1 is a permissive fallback. UTF-16 or Windows-1252 exports may need to be re-saved as UTF-8.

---

## Implementation Notes

- **Backend module:** [backend/app/api/user_check.py](backend/app/api/user_check.py), mounted in [backend/app/main.py](backend/app/main.py) with prefix `/user-check`.
- **Backend LSVT calls:** only `list_users` (paginated). No cache; each check triggers one full pass.
- **Frontend view:** [frontend/src/views/CheckUsersPage.vue](frontend/src/views/CheckUsersPage.vue), Tailwind/slate/emerald styling consistent with the other User Training Data views.
