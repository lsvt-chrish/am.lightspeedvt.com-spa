# Certifications Feature

## Overview

The **Certifications** feature lets authenticated users (those with API credentials in session) explore and report on LightSpeed VT certifications and their completion status. Users can view which learners have completed a given certification, or view all certifications completed by a specific learner.

The feature is backed by the LightSpeed VT REST API. Authentication uses **session-based API credentials** (API key and secret) entered via the app’s **Credentials** panel. There is no separate “API configuration page”; credentials are managed via the global Credentials drawer (sidebar). A “Clear credentials” action is available from the Credentials drawer to remove stored API key/secret.

---

## User Flows

### Entry and Authentication

- **URL prefix:** `/certifications` (Vue Router).
- **Entry point:** Visiting `/certifications` shows a **choice page**. The frontend calls `GET /session/credentials`. If `has_credentials` is false, the page shows a message and a control to open the Credentials drawer so the user can enter API key and secret; once credentials are saved, the user can use the certification flows.
- **Session:** API key and secret are stored in the app session (signed cookie + in-memory store) after the user saves them in the Credentials panel. See [backend/app/session.py](backend/app/session.py) and [backend/app/api/session.py](backend/app/api/session.py).

### Two Main Modes

From the choice page, the user picks one of two views:

1. **View users for a certification** — “Who has completed certification X?”
2. **View certifications for a user** — “What certifications has user Y completed?”

---

## Feature 1: View Users for a Certification

**Purpose:** List all users who have **completed** a specific certification.

### Flow

1. User clicks the option to view users for a certification on the choice page → navigates to the “view users for certification” view (e.g. `/certifications/by-certification`).
2. **Certification list (GET):**
   - The frontend calls the backend `GET /api/certifications`. The backend uses session credentials to call the LightSpeed VT API (`GET .../certifications` with optional pagination, e.g. `itemsPerPage=200`).
   - Optionally, the backend fetches the **completion count** (number of users who completed each certification) via the certification users report endpoint. Counts can be fetched in batch with limited concurrency and small delays to avoid overloading the API.
   - Response shapes are normalized (handles both list and dict wrappers such as `data`, `certifications`, `items`). Certifications are returned to the frontend.
3. **UI:** Certifications are shown as **tiles** (or list) with certification ID, name, optional description snippet, and **user count** (e.g. “N users completed”). A search bar filters tiles by certification name, ID, or description (client-side).
4. **Select certification:** User clicks a tile (or selects a certification) → frontend calls `GET /api/certifications/{cert_id}/users/report` with pagination params.
5. **User list:**
   - The backend calls the **certification users report** endpoint for that certification ID: `GET .../certifications/{cert_id}/users/report` (with pagination parameters).
   - The response is normalized (list vs dict with `data`, `users`, `items`). Only rows with a non-null **completeDate** are kept (i.e. completed completions only).
   - Results are returned to the frontend and displayed in a table: #, Name, Username, Email, and an action **“View Certificate”** that opens the LightSpeed VT share URL for that user and certification.

### Data Shown (per user)

- Name (firstName, lastName)
- Username
- Email
- Link to view the certificate (external LightSpeed VT URL)

### Rate Limiting

- The certification list and report routes are limited to **10 requests per minute** per client (same approach as APL: in-handler in-memory rate limit or optional slowapi).

---

## Feature 2: View Certifications for a User

**Purpose:** List all certifications that a **specific user** has completed.

### Flow

1. User clicks the option to view certifications for a user on the choice page → navigates to the “view certifications for user” view (e.g. `/certifications/by-user`).
2. **Form (GET):** A form is shown with a single field: **User ID**.
3. **Submit:** User submits the form with a user ID (e.g. POST or GET with query param).
4. **Lookup logic:**
   - The backend fetches **all** certifications (same as in Feature 1).
   - For **each** certification, it fetches the certification users report and checks whether the given user ID appears in that report with a non-null **completeDate**.
   - This is done with limited concurrency (e.g. a small pool and short delays between requests) to avoid rate limits.
   - Matching completions are collected and normalized into a list of “user certification” objects (certification ID, name, completion date, and related user/report fields).
5. **Results:** Certifications are sorted by completion date (latest first) and displayed in a table: #, Certification ID, Certification Name, Completion Date, and a **“View Certificate”** link to the LightSpeed VT share URL.

### Data Shown (per certification)

- Certification ID and name
- Completion date
- Link to view the certificate

### Performance Notes

- Because “certifications for user” requires checking every certification’s report, the first load can take a while. The UI shows a loading state and a message that the search may take a moment.
- **Caching:** The backend can cache “certifications for user” by user ID (in-memory, TTL configurable) to avoid re-scanning on repeated requests for the same user.
- **Rate limiting:** The route is limited to **10 requests per minute** per client.

---

## API Integration

### LightSpeed API Client

The feature uses a backend **LightSpeed API client** (e.g. [backend/app/lightspeed_api.py](backend/app/lightspeed_api.py) or `certifications_client.py`) that:

- **Authentication:** Builds a Basic auth header from API key and secret: `Base64(api_key:api_secret)`.
- **Credentials:** Receives API key and secret from the calling route (read from `request.state.session`). All certification API routes require valid session credentials and return **401** if missing.
- **Base URL:** `https://webservices.lightspeedvt.net/REST/V1`
- **HTTP client:** Uses **httpx** (async, consistent with [backend/app/lsvt_user.py](backend/app/lsvt_user.py) and [backend/app/api/scan.py](backend/app/api/scan.py)).

### Endpoints Used

| Purpose | Method / Endpoint | Notes |
|--------|--------------------|--------|
| List certifications | `GET /certifications` | Optional query params e.g. `itemsPerPage`, `page`. Response may be list or dict with `data` / `certifications` / `items`. |
| Certification users report | `GET /certifications/{cert_id}/users/report` | Pagination: `itemsPerPage=200`, `page=1`. Returns users with completion data; only rows with `completeDate` are treated as completed. |

### Response Handling

- Certification list and report payloads are normalized to support multiple response shapes (list vs dict with `data`, `users`, or `items`).
- Certification IDs are read from fields such as `certificationId`, `id`, or `certId`; names from `certificationName`, `name`, or `title`.
- User identifiers in reports are matched using `userId` or `id`; completion is determined by presence of `completeDate`.

---

## Backend Routes Summary (this app)

| Backend route | Methods | Description |
|---------------|--------|-------------|
| `GET /api/certifications` | GET | List certifications (and optionally counts). Requires session credentials; returns 401 if missing. |
| `GET /api/certifications/{cert_id}/users/report` | GET | Users who completed certification `cert_id` (paginated). Requires session credentials. |
| `GET /api/certifications/by-user/{user_id}` (or query param) | GET | List certifications completed by user `user_id`. Requires session credentials; may call list + N reports internally. |

All certification routes **require valid session credentials** (same pattern as [backend/app/api/session.py](backend/app/api/session.py) `_has_credentials`). Return **401** when credentials are missing so the frontend can prompt the user to open the Credentials drawer.

---

## Frontend Routes and Views (this app)

| Vue route | View | Description |
|-----------|------|-------------|
| `/certifications` | CertificationsChoicePage.vue | Choice page: two cards/links — “View users for certification”, “View certifications for user”. If no credentials, show prompt and control to open Credentials drawer. |
| `/certifications/by-certification` | CertificationsByCertPage.vue | Step 1: list certifications (tiles/list + search). Step 2: after selection, table of users with “View Certificate” links. |
| `/certifications/by-user` | CertificationsByUserPage.vue | Form: User ID. On submit, table of certifications completed by that user with “View Certificate” links. |

Add a sidebar link **“Certifications”** in [frontend/src/App.vue](frontend/src/App.vue) and register the above routes in [frontend/src/router.js](frontend/src/router.js).

---

## Caching and Performance

- **Certification list:** Cached in the backend via an in-memory cache keyed by request options; TTL is configurable (e.g. `CERTIFICATIONS_CACHE_TTL` or `API_CACHE_TTL`).
- **User count per certification:** Optional; if implemented, fetch in batch with limited concurrency and cache by certification ID.
- **Certifications for user:** Cached in-memory keyed by user ID; TTL configurable (`CERTIFICATIONS_USER_CACHE_TTL`).
- **Concurrency:** Batch operations use limited parallelism and short delays between requests to reduce API rate-limit and timeout risk.

---

## Security and Validation

- **Session credentials:** All certification API routes read `request.state.session` and require `api_key` and `api_secret`; else return **401**.
- **Rate limiting:** Certification list, report, and “by-user” routes are limited to **10 requests per minute** per client (implement as in [backend/app/api/apl.py](backend/app/api/apl.py) or with slowapi).
- **Validation:** Validate and sanitize `cert_id` and `user_id` (e.g. non-empty, safe for URL); use them only in backend API calls and responses.

---

## Configuration

Add to [backend/app/config.py](backend/app/config.py) (env-based):

- **CERTIFICATIONS_CACHE_TTL** (or **API_CACHE_TTL**) — TTL in seconds for certification list (and optionally counts).
- **CERTIFICATIONS_USER_CACHE_TTL** — TTL for “certifications for user” cache.
- **LIGHTSPEED_API_TIMEOUT** (or **API_TIMEOUT**) — Timeout in seconds for outbound requests to LightSpeed VT REST API.

---

## Dependencies

- **Backend:** FastAPI (Request, APIRouter, HTTPException), httpx, existing session middleware and session API. No new framework dependencies; optional slowapi for rate limiting if preferred over custom in-handler limiting.
- **Frontend:** Vue Router, fetch with `credentials: 'include'`, existing Tailwind/slate/emerald styling. No new UI framework.

---

## Implementation Notes (this project)

- **Backend:** FastAPI router lives under `app.api.certifications` (e.g. [backend/app/api/certifications.py](backend/app/api/certifications.py)), mounted with prefix such as `/api/certifications` so that list is `GET /api/certifications`, report is `GET /api/certifications/{cert_id}/users/report`, and by-user is `GET /api/certifications/by-user/{user_id}` or with query param.
- **Frontend:** Vue views live under `frontend/src/views/` (CertificationsChoicePage.vue, CertificationsByCertPage.vue, CertificationsByUserPage.vue). Styling matches the rest of the app (Tailwind, slate/emerald as in [frontend/src/App.vue](frontend/src/App.vue) and [frontend/src/views/LinkBuilderPage.vue](frontend/src/views/LinkBuilderPage.vue)).
- **LightSpeed API client:** Single backend module in `backend/app/` (e.g. `lightspeed_api.py` or `certifications_client.py`) using httpx and session credentials; Basic auth built from `api_key:api_secret`.
- **Patterns:** Reuse session credential check from [backend/app/api/session.py](backend/app/api/session.py); rate limiting and in-memory caching patterns from [backend/app/api/apl.py](backend/app/api/apl.py) and [backend/app/lsvt_user.py](backend/app/lsvt_user.py).

---

## Summary

The Certifications feature provides two main workflows: (1) **certification → users** (who completed this certification?) and (2) **user → certifications** (what certifications did this user complete?). Both use the LightSpeed VT certifications and certification users report APIs, with caching and controlled concurrency to improve performance and respect rate limits. Access is gated on session-based API credentials; the frontend uses the existing Credentials drawer when credentials are missing. UI is implemented as Vue views with Tailwind, with a clear entry (choice page), navigation, and optional credential clearing via the global Credentials panel.
