# VetComm LMS Statement Generation API

Partner-facing contract for generating 400-character VA-ready personal statements.

Share this document with LMS engineering, plus credentials via a secure channel (1Password or equivalent). Do **not** share Anthropic keys, system prompts, or internal implementation notes.

## Endpoint

```
POST {base_url}/api/v1/statements/generate
```

| Environment | `base_url` |
|-------------|----------------------|
| Staging | `https://stage-portal.vetcomm.link` |
| Production | `https://portal.vetcomm.org` |

## Credentials (what VetComm sends you)

| Item | Description |
|------|-------------|
| **API key** | `vc_lms_{prefix}_{secret}` — send as Bearer token |
| **HMAC secret** | Shared secret for `X-VetComm-Signature` |
| **Rate limit** | Default 60 requests per minute per key |

Production and staging partner keys require HMAC. Invalid key or signature → `401`.

## Authentication

### Headers

```
Authorization: Bearer {api_key}
Content-Type: application/json
X-VetComm-Signature: sha256={hex_digest}
```

### HMAC signature

1. Take the **exact raw request body bytes** you will send (no pretty-print changes after signing).
2. Compute `HMAC-SHA256(body, hmac_secret)` as lowercase hex.
3. Send `X-VetComm-Signature: sha256={hex}`.

Use constant-time comparison on your side when verifying responses is not required; only the request is signed.

## Request body

```json
{
  "request_id": "lms_20260716_abc123",
  "condition": {
    "name": "Right knee strain",
    "category": "knee",
    "claim_path": "new"
  },
  "veteran_input": {
    "in_service_cause": "Served in infantry, did heavy lifting and ruck marches during my time in service.",
    "what_developed": "During my second year of service my right knee started swelling and having sharp pain. It got worse over deployments.",
    "medical_care_during_service": "Went to medical in Okinawa. They gave me ibuprofen and told me to rest.",
    "current_impact": "Can't stand more than 15 minutes without pain. Need a handrail on stairs. Take ibuprofen daily. Had to switch to a desk job."
  },
  "regeneration": null
}
```

### Fields

| Field | Required | Notes |
|-------|----------|-------|
| `request_id` | yes | String ≤64 chars. LMS-generated; echoed in the response. |
| `condition.name` | yes | Free text condition name from the veteran. |
| `condition.category` | yes | Enum — see list below. |
| `condition.claim_path` | yes | `new` \| `increase` \| `supplemental` \| `secondary` |
| `veteran_input.in_service_cause` | yes | What they did in service that caused the condition. |
| `veteran_input.what_developed` | yes | What emerged, when, how it progressed. |
| `veteran_input.medical_care_during_service` | no | Omit or `""` if none. |
| `veteran_input.current_impact` | yes | How it affects them today. |
| `regeneration` | no | `null` on first attempt; object on regenerations (see below). |

Grammar/spelling in `veteran_input` do not need to be clean; the generator normalizes.

### `condition.category` values

`hearing_loss`, `tinnitus`, `ptsd`, `mst`, `depression_anxiety`, `tbi`, `sleep_apnea`, `foot`, `ankle`, `knee`, `hip`, `back_spine`, `shoulder`, `nerve_damage`, `heart`, `hypertension`, `sinusitis_rhinitis`, `asthma`, `gerd`, `migraine`, `other`

## Regeneration

1. Call the endpoint → show statement to the veteran.
2. Veteran asks for edits (“add X”, “remove Y”).
3. Call again with `regeneration` populated.
4. Up to **5 attempts** per condition (`attempt_number` 1–5). Attempt 1 has `regeneration: null`.

```json
"regeneration": {
  "previous_statement": "In service in the infantry, I did heavy lifting...",
  "veteran_feedback": "Add that the pain is worse in cold weather. Remove the part about ibuprofen.",
  "attempt_number": 2
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `previous_statement` | yes | Exact statement from the prior response (≤400 chars). |
| `veteran_feedback` | yes | What to change, in the veteran’s words. |
| `attempt_number` | yes | Integer `2`–`5`. |

`attempt_number > 5` → `400` with `regeneration_limit_exceeded`.

Feedback is an **edit instruction** on top of the original `veteran_input`, not a replacement of it.

## Responses

### 200 Success

```json
{
  "request_id": "lms_20260716_abc123",
  "status": "success",
  "statement": "As an infantryman, I performed heavy lifting...",
  "character_count": 350,
  "attempt_number": 1,
  "generated_at": "2026-07-17T20:30:28+00:00"
}
```

- `statement` — plain text only. No headers, certification clause, markdown, or em dashes. Paste-ready for VA.gov.
- `character_count` — always ≤400; target 350–395.
- `attempt_number` — `1` for initial, `2`–`5` for regenerations.

### Errors

| HTTP | `error.code` | When |
|------|--------------|------|
| 400 | `insufficient_input` | Missing/empty/invalid required fields. May include `required_fields_missing`. |
| 400 | `regeneration_limit_exceeded` | `attempt_number` > 5. |
| 400 | `generation_failed_quality` | Could not produce a compliant ≤400 statement; collect more detail. |
| 401 | `unauthorized` | Missing/invalid API key or HMAC signature. |
| 429 | (throttle) | Rate limit exceeded (default 60/min). |
| 500 | `internal_error` | Transient failure; `retryable: true` — retry the request. |

Example:

```json
{
  "request_id": "lms_20260716_abc123",
  "status": "error",
  "error": {
    "code": "insufficient_input",
    "message": "Veteran input is too sparse to generate a compliant statement.",
    "required_fields_missing": ["current_impact"]
  }
}
```

## Signed curl example

Replace `{base_url}`, `{api_key}`, and `{hmac_secret}`. Sign the **same file** you POST.

```bash
cat > /tmp/lms-request.json <<'EOF'
{
  "request_id": "smoke_001",
  "condition": {
    "name": "Right knee strain",
    "category": "knee",
    "claim_path": "new"
  },
  "veteran_input": {
    "in_service_cause": "Served in infantry, heavy lifting and ruck marches.",
    "what_developed": "Right knee started swelling and sharp pain in year two. Worsened over deployments.",
    "medical_care_during_service": "Medical in Okinawa, ibuprofen and rest.",
    "current_impact": "Cannot stand more than 15 minutes without pain. Handrail on stairs. Daily ibuprofen. Switched to desk job."
  },
  "regeneration": null
}
EOF

SIGNATURE=$(openssl dgst -sha256 -hmac "{hmac_secret}" /tmp/lms-request.json | awk '{print "sha256="$2}')

curl -sS -X POST "{base_url}/api/v1/statements/generate" \
  -H "Authorization: Bearer {api_key}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-VetComm-Signature: ${SIGNATURE}" \
  --data-binary @/tmp/lms-request.json
```

Use `--data-binary @file` so the body bytes match the signature.

## Output quality (fixed; not configurable)

- Audience: VA rater (not the veteran).
- First person, factual; no exaggeration.
- Structure: in-service cause → what developed → medical care (if provided) → current impact.
- Character target 350–395; hard cap 400.
- No em dashes, emojis, or markdown.

## Data handling

Veteran input and generated statements are **not stored**. Only anonymous metadata is retained for monitoring (`request_id`, timestamp, category, claim path, attempt number, status code, character count).

## Suggested integration checks

1. Happy path (knee / `new`) → `200`, `character_count` ≤ 400.
2. Wrong API key or bad HMAC → `401`.
3. Missing `current_impact` → `400` `insufficient_input`.
4. Regeneration attempt 2 with feedback → `200`, `attempt_number: 2`.
5. `attempt_number: 6` → `400` `regeneration_limit_exceeded`.
6. Spot-check categories: `ptsd`, `tinnitus`, `back_spine`, and `claim_path: secondary`.
