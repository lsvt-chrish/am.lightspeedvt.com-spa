# VetComm Statement Generator - Design Documentation

## Overview

The VetComm Statement Generator lets a veteran (or an LSVT staff member on their behalf) enter a disability condition and four pieces of narrative input, then generates a VA-ready personal statement by calling VetComm's statement generation API. The statement is displayed for copy/paste into VA.gov, with support for up to 5 regeneration attempts based on veteran feedback.

This app acts purely as a **proxy**: it holds the VetComm API key/secret (supplied by VetComm), forwards the request, and returns the result. Nothing is persisted — no database models, no history, no stored statements. This mirrors VetComm's own data handling (see `docs/lms-statement-api.md`), which discards raw request content after each call.

## Embedding

This page is designed to be **iframed into LightSpeed VT**, not used as a standalone app page:

- It is **not linked from any nav/hub page** in this app — reachable only via its direct URL, `/vetcomm/statements`.
- The route sets `meta: { chromeless: true }` in `frontend/src/router.js`, and `App.vue` hides the app's sidebar (`v-if="!route.meta.chromeless"`) when that flag is set, so the iframe shows only the form/result content.

## Architecture

### Components (this project: FastAPI + Vue SPA)

1. **Statement Generator UI** (`/vetcomm/statements`, `frontend/src/views/VetCommStatementPage.vue`)
   - Form for condition name, category, claim path, and the four `veteran_input` fields
   - Category and claim path options are hardcoded from the spec's fixed enums (20 categories, 4 claim paths) — not fetched from the backend, since these are stable, VetComm-defined lists
   - On submit, calls the backend proxy via `fetch('/api/vetcomm/statements', ...)`
   - Displays the returned statement, character count, and attempt number, with a **Copy** button (`navigator.clipboard.writeText`) that flips to "Copied!" for 2 seconds
   - Regenerate control: a feedback textarea that resends the previous statement + feedback + incremented `attempt_number`; disabled after attempt 5
   - Errors are shown as a simple inline banner with VetComm's message text; `insufficient_input` errors additionally list the missing fields

2. **Proxy endpoint** (`POST /vetcomm/statements`, `backend/app/api/vetcomm.py`)
   - Accepts `condition`, `veteran_input`, and optional `regeneration` (validated via pydantic models mirroring the spec's shapes)
   - Generates the `request_id` server-side (`lms_<uuid hex>`) — the frontend never needs to construct one
   - Calls `app/vetcomm_api.py` and translates `VetCommError` into an HTTP response
   - No admin auth — this is not an admin action, it's a user-facing tool meant to be embedded

3. **VetComm client** (`backend/app/vetcomm_api.py`)
   - `httpx.AsyncClient`-based, following the same pattern as `lightspeed_api.py`
   - Sends `Authorization: Bearer {api_key}`
   - Optionally computes and sends `X-VetComm-Signature: sha256={hmac}` when a shared secret is configured (HMAC-SHA256 over the raw request body)
   - Raises `VetCommError(code, message, status_code, details)` on any non-success response so the route layer can map it to the right HTTP status and surface VetComm's error code/message/details to the frontend

## Request Flow

1. User fills out the form and submits
2. Frontend POSTs `{condition, veteran_input, regeneration: null}` to `/api/vetcomm/statements`
3. Backend generates a `request_id`, calls VetComm's `POST /v1/statements/generate`
4. On success, backend returns `{statement, character_count, attempt_number}`
5. Frontend displays the statement; user can submit feedback to regenerate (attempts 2-5), which resends `previous_statement` + `veteran_feedback` + `attempt_number`
6. On error (insufficient input, quality failure, regeneration limit, auth failure, VetComm internal error), backend returns an HTTP error with VetComm's `code`/`message` in the body; frontend shows it inline

## Configuration

### Environment Variables (`backend/app/core/config.py`)

```python
app_env: str = "development"                              # "development" | "production"; drives the base_url default below
vetcomm_api_base_url: str | None = None                    # host only; unset -> derived from app_env, see below
vetcomm_api_key: str = ""                                  # VetComm-supplied Bearer token
vetcomm_shared_secret: str = ""                             # optional, enables HMAC request signing
vetcomm_api_timeout: int = 30                                # seconds
```

`vetcomm_api_base_url` is left unset by default so it auto-selects per environment: `app_env=development` → `https://stage-portal.vetcomm.link`, `app_env=production` → `https://portal.vetcomm.org` (`backend/app/core/config.py`'s `default_vetcomm_base_url` validator). The client appends `/api/v1/statements/generate` (`backend/app/vetcomm_api.py`). Set `VETCOMM_API_BASE_URL` explicitly in `.env` to override this (e.g. to point a local machine at prod).

A separate validator (`require_real_secret_key_in_production`) refuses to start when `app_env=production` and `secret_key` is still the dev default — a safety net against deploying with the wrong session secret.

`.env` is gitignored in this repo (no `.env.example` exists); the real key/secret must be added to the deployment's `.env`/`.env.prod` once VetComm provides them, along with `APP_ENV=production` for prod. Leaving `vetcomm_shared_secret` empty simply omits the `X-VetComm-Signature` header (signing is optional per the spec).

## Error Handling

VetComm's structured error codes are passed straight through to the frontend inside the HTTP error body (`{code, message, ...details}`):

| VetComm code | HTTP status returned | Notes |
|---|---|---|
| `insufficient_input` | 400 | `required_fields_missing` list shown under the error banner |
| `regeneration_limit_exceeded` | 400 | Frontend also disables the Regenerate button at attempt 5 client-side |
| `generation_failed_quality` | 400 | Rare; message asks for more detail |
| `unauthorized` | 401 | Invalid API key/signature — a deployment config issue, not a user error |
| (throttle) | 429 | Passed through as-is so the caller can back off, per rate limit |
| `internal_error` (or unrecognized) | 502 | VetComm-side failure; `retryable` flag passed through when present |

## Data Handling

No veteran input, generated statements, or attempt history are stored in this app's database — every request is proxied and discarded, consistent with VetComm's own no-storage policy. There is currently no database table, migration, or logging of statement content associated with this feature.

## Testing Considerations

This repository has no existing test suite (no `tests/` directory, no pytest config) — none was added for this feature. If tests are introduced later, priorities would be:

1. Client module: request body shape, Bearer header, HMAC signature computation, error-code-to-`VetCommError` mapping
2. Proxy route: pydantic validation of condition/veteran_input/regeneration, `request_id` generation, HTTP status mapping per error code
3. Frontend: form validation (`canSubmit`), attempt-number increment on regenerate, disabling regenerate past attempt 5

## Future Enhancements

1. Admin-configurable category/claim-path lists if VetComm's enums start changing more often
2. Optional statement history/audit logging if a future compliance requirement needs it
3. A lightweight loading/rate-limit indicator if VetComm imposes per-key rate limits later
