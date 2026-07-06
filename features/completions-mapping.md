# Map User Completions Feature

## Overview

The **Map User Completions** feature lets authenticated users copy **chapter-level course completions** from one LightSpeed VT user account to another within the **same system** (same API key + secret). The typical use case: a learner has two accounts, and the completion history from account A needs to be transferred onto account B.

The feature has two phases:

1. **Preview** — fetch the source user's chapters and the destination user's chapters, then classify each source chapter as `new` (missing on destination) or `existing` (already present on destination).
2. **Apply** — write the user-selected chapters onto the destination user via `POST /users/{userId}/trainingInfo`. The user picks a conflict mode (`skip` or `overwrite`) at run time.

Authentication uses **session-based API credentials**, the same pattern as the certifications and training-export features.

---

## User Flow

### Entry and Authentication

- **URL:** `/user-training-data/map-completions` (Vue Router).
- **Entry point:** the **User Training Data** choice page ([frontend/src/views/CertificationsChoicePage.vue](frontend/src/views/CertificationsChoicePage.vue)) shows a **Map user completions** card alongside the existing certification flows. If `has_credentials` is `false`, the choice page directs the user to the Credentials drawer first.

### Mapping Flow

1. User enters **Source user ID**, **Destination user ID**, and an optional **Start date** / **End date**, then clicks **Preview**.
2. The frontend calls `GET /api/completions-mapping/preview?source_user_id=…&destination_user_id=…&start_date=…&end_date=…`. The backend fetches `GET /users/{userId}/trainingInfo` for each user (in parallel via `asyncio.gather`), passing `start` / `end` through to LSVT, and returns a flat list of source chapters annotated with `status: "new" | "existing"` and the destination's existing row when applicable.
3. The frontend renders a table (`Course | Chapter | Source date | Status | Destination date | Result`) plus a summary (source total, destination total, new count, existing count).
4. The user:
   - Picks a **conflict mode** — `Skip existing` (default, safe) or `Overwrite existing`.
   - Selects which chapters to transfer (defaults to all `new` rows; "Select all", "Select all new", and "Clear" shortcuts available).
   - Clicks **Apply mapping**.
5. The frontend POSTs the selection to `/api/completions-mapping/apply`. The backend re-fetches the destination's existing chapters (don't trust the client), enforces the conflict mode, and calls `POST /users/{destination_user_id}/trainingInfo` per selected chapter with limited concurrency (semaphore = 5, ~100 ms delay between writes).
6. The response includes `created`, `skipped`, `failed`, and a per-chapter results array. Each row in the table is updated with its outcome.

### Conflict Modes

| Mode | Behavior on chapters already present on destination |
|------|------------------------------------------------------|
| `skip` (default) | Server skips the write and reports `skipped: true`. |
| `overwrite` | Server still POSTs to `/users/{id}/trainingInfo`. The actual semantics depend on LSVT (overwrite vs duplicate vs ignore). |

---

## API Integration

### LightSpeed VT Endpoints Used

| Purpose | Method / Endpoint | Notes |
|---------|--------------------|-------|
| Read source / destination training info | `GET /users/{userId}/trainingInfo` | Already wrapped by `get_user_training_info` in [backend/app/lightspeed_api.py](backend/app/lightspeed_api.py). |
| Write a chapter completion | `POST /users/{userId}/trainingInfo` | Wrapped by `post_user_training_info` in [backend/app/lightspeed_api.py](backend/app/lightspeed_api.py). Body shape produced by `_chapter_post_body`. |

### Open Question: POST Body Schema

The public reference at [LightspeedVT API Docs — User Training Info (POST)](https://lightspeedvt.readme.io/reference/postusertraininginfo) does not render its body params on the public page (only confirms the `userId` path param and the `boolean` 200 response). The current implementation mirrors the GET response shape:

```json
{
  "courseId": "<id>",
  "chapterId": "<id>",
  "chapterAttemptDate": "YYYY-MM-DDTHH:MM:SS",
  "chapterAttemptScore": 100,
  "chapterAttemptStatus": "Completed"
}
```

If the first live test returns `400`, the only thing that needs to change is `_chapter_post_body` in [backend/app/lightspeed_api.py](backend/app/lightspeed_api.py) (e.g. wrap as `{"userCourseChapters": [...]}` or rename fields).

---

## Backend Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/completions-mapping/preview` | `GET` | Diff source vs destination chapters. Query params: `source_user_id`, `destination_user_id`, optional `start_date` / `end_date` (`YYYY-MM-DD`). |
| `/api/completions-mapping/apply` | `POST` | Apply selected chapters to destination. Body: `{source_user_id, destination_user_id, conflict_mode, chapters[], start_date?, end_date?}`. The destination re-fetch uses the same date window so the conflict check matches what the user previewed. |

Both routes:

- Require valid session credentials (`request.state.session["api_key"]` and `api_secret`); return **401** otherwise.
- Are rate limited to **10 requests per minute per client IP** (custom in-memory limiter, mirrors [backend/app/api/training_export.py](backend/app/api/training_export.py)).
- Validate `source_user_id` and `destination_user_id` with the shared `_safe_id` regex (alphanumeric, dash, underscore) and reject identical values.

---

## Frontend Routes and Views

| Vue route | View | Description |
|-----------|------|-------------|
| `/user-training-data/map-completions` | [frontend/src/views/CompletionsMappingPage.vue](frontend/src/views/CompletionsMappingPage.vue) | Form, preview table, conflict mode, apply + per-row results. |

Entry point: a card titled **Map user completions** on [frontend/src/views/CertificationsChoicePage.vue](frontend/src/views/CertificationsChoicePage.vue).

---

## Performance and Safety Notes

- **Concurrency:** writes use `asyncio.Semaphore(5)` plus a 100 ms delay between completions (matches the pacing used in [backend/app/api/training_export.py](backend/app/api/training_export.py)).
- **Server-enforced conflict mode:** the apply endpoint re-fetches the destination's existing chapters every run; the client cannot bypass `skip`.
- **No caching:** the preview endpoint is intentionally uncached so the user always sees a fresh diff.
- **No DB persistence:** mappings are not stored locally. Each run is independent.
- **Date window:** LSVT's `GET /users/{userId}/trainingInfo` defaults to **the current month** when no `start` / `end` are passed, so older completions never appear in the preview unless a window is supplied. The frontend defaults the inputs to `today − 1 year` → `today`; clearing both fields falls back to LSVT's current-month default. Both `preview` and `apply` accept the same `start_date` / `end_date` to keep the conflict check aligned with what was previewed.

---

## Security and Validation

- **Session credentials:** required for both routes; missing → 401.
- **ID validation:** both `source_user_id` and `destination_user_id` must match `^[a-zA-Z0-9_\-]+$` and must differ.
- **Rate limiting:** 10 req/min per client IP.
- **Error surfacing:** per-chapter failures include the LSVT HTTP status and a truncated response body so issues like missing course access on the destination user are visible in the UI.

---

## Implementation Notes

- **Backend module:** [backend/app/api/completions_mapping.py](backend/app/api/completions_mapping.py), mounted in [backend/app/main.py](backend/app/main.py) with prefix `/completions-mapping`.
- **Client extension:** `post_user_training_info` and `_chapter_post_body` added to [backend/app/lightspeed_api.py](backend/app/lightspeed_api.py); same Basic-auth + httpx pattern as the existing readers.
- **Frontend view:** [frontend/src/views/CompletionsMappingPage.vue](frontend/src/views/CompletionsMappingPage.vue), Tailwind/slate/emerald styling consistent with the existing User Training Data views.
