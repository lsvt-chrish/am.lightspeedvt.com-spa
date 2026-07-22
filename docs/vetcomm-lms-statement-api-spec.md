# VetComm Statement Generation API

## Endpoint

```
POST https://api.vetcomm.us/v1/statements/generate
```

## Authentication

Bearer token in the Authorization header. One API key per LMS partner.

```
Authorization: Bearer {api_key}
```

Optional HMAC signature verification (recommended for production):

```
X-VetComm-Signature: sha256={hex_digest}
```

Signature computed as `HMAC-SHA256(raw_request_body, shared_secret)`. Invalid signature returns 401.

## Request

### Headers

```
Authorization: Bearer {api_key}
Content-Type: application/json
X-VetComm-Signature: sha256={hex} (if signing enabled)
```

### Body

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

### Field definitions

**`request_id`** (required, string, ≤64 chars). LMS-generated ID for tracing. Echoed back in the response.

**`condition.name`** (required, string). The condition being claimed. Free text, sent verbatim as collected from the veteran.

**`condition.category`** (required, enum). Drives generation logic and category-specific handling. One of:

- `hearing_loss`
- `tinnitus`
- `ptsd`
- `mst`
- `depression_anxiety`
- `tbi`
- `sleep_apnea`
- `foot`
- `ankle`
- `knee`
- `hip`
- `back_spine`
- `shoulder`
- `nerve_damage`
- `heart`
- `hypertension`
- `sinusitis_rhinitis`
- `asthma`
- `gerd`
- `migraine`
- `other`

**`condition.claim_path`** (required, enum). One of:

- `new`
- `increase`
- `supplemental`
- `secondary`

**`veteran_input`** (required, object). Four fields collected from the veteran by the LMS. Grammar and spelling do not need to be clean; the generation model normalizes.

- **`in_service_cause`** (required, string). What the veteran was doing during service that caused the condition.
- **`what_developed`** (required, string). What symptom or condition emerged, when, how it progressed.
- **`medical_care_during_service`** (optional, string). Whether they got medical care during service and what it was. Omit or empty string if none.
- **`current_impact`** (required, string). How the condition affects them today.

**`regeneration`** (optional, object, nullable). Present only when the veteran wants to regenerate a prior statement with edits. See "Regeneration" below.

```json
"regeneration": {
  "previous_statement": "In service in the infantry, I did heavy lifting...",
  "veteran_feedback": "Add that the pain is worse in cold weather. Remove the part about ibuprofen.",
  "attempt_number": 2
}
```

## Regeneration

The LMS can request a regenerated statement based on veteran feedback. Flow:

1. LMS calls the endpoint, gets a statement.
2. LMS shows the statement to the veteran.
3. Veteran says "add X" / "remove Y" / "make it clearer that Z."
4. LMS calls the endpoint again with the `regeneration` object populated.
5. Repeat up to 5 attempts per condition.

**Regeneration fields:**

- **`previous_statement`** (required, string). The exact statement returned by the prior call.
- **`veteran_feedback`** (required, string). What the veteran wants changed, in their own words.
- **`attempt_number`** (required, integer, 2-5). Which attempt this is. First generation is attempt 1 (no `regeneration` object). Second through fifth include `regeneration` with `attempt_number: 2` through `5`.

Requests with `attempt_number > 5` return 400 with `regeneration_limit_exceeded`.

The generation model treats regeneration input as an edit instruction on top of the original `veteran_input`, not a replacement. Original workbook inputs are still authoritative; feedback shifts emphasis or corrects specifics.

## Response

### 200 Success

```json
{
  "request_id": "lms_20260716_abc123",
  "status": "success",
  "statement": "In service in the infantry, I did heavy lifting and ruck marches. During my second year my right knee developed swelling and sharp pain, treated at medical in Okinawa. Today I cannot stand more than 15 minutes without pain, need a handrail on stairs, take daily ibuprofen, and had to switch to a desk job.",
  "character_count": 302,
  "attempt_number": 1,
  "generated_at": "2026-07-16T14:32:00Z"
}
```

**`statement`** is the finished output. No headers, no certification clause, no formatting. Directly paste-able into VA.gov.

**`character_count`** is the exact character count. Always ≤400, targeting 350-395.

**`attempt_number`** echoes the attempt number of this generation (1 for initial, 2-5 for regenerations).

### 400 Insufficient input

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

Returned when required fields are missing or empty.

### 400 Regeneration limit exceeded

```json
{
  "request_id": "lms_20260716_abc123",
  "status": "error",
  "error": {
    "code": "regeneration_limit_exceeded",
    "message": "Maximum of 5 attempts per condition. Use the last returned statement or start a new request with revised veteran_input."
  }
}
```

### 400 Cannot produce compliant statement

```json
{
  "request_id": "lms_20260716_abc123",
  "status": "error",
  "error": {
    "code": "generation_failed_quality",
    "message": "Unable to produce a statement meeting VA quality standards within 400 characters from the provided input."
  }
}
```

Returned when the generation model cannot produce a statement that meets VA tone and completeness standards within the character cap. Rare; typically when input is contradictory or extremely sparse. LMS should collect more detail from the veteran.

### 401 Unauthorized

```json
{ "status": "error", "error": { "code": "unauthorized", "message": "Invalid API key or signature." } }
```

### 500 Internal error

```json
{
  "request_id": "lms_20260716_abc123",
  "status": "error",
  "error": {
    "code": "internal_error",
    "message": "Statement generation failed. Retry the request.",
    "retryable": true
  }
}
```

## Voice and quality standards

Every generated statement conforms to these standards. None of them are configurable by the LMS.

- **VA-audience tone.** Written for a VA rater to evaluate the claim. Not written for the veteran to feel good about. The goal is a C&P appointment and a favorable rating decision.
- **First person, factual.** No dramatic language, no exaggeration.
- **Structured pattern.** In-service cause, then what developed, then (if available) medical care during service, then current impact.
- **Rating-criteria-aligned language** for current impact where the workbook prescribes it (mental health especially).
- **Character range 350-395** targeted; hard cap 400.
- **No em dashes, no emojis, no markdown.**

## Data handling

VetComm does not store veteran input or generated statements. Each request is generated, returned, and discarded. Only anonymous request metadata (request_id, timestamp, category, attempt number, response code) is retained for operational monitoring.

Raw content never persists on VetComm infrastructure beyond the duration of the request.
