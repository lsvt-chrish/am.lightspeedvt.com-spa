# VetComm LMS Buddy Statement Generation API

Partner-facing contract for generating VA-ready lay/witness (buddy) statements in the witness's first-person voice.

Share this document with LMS engineering, plus credentials via a secure channel (1Password or equivalent). Do **not** share Anthropic keys, system prompts, or internal implementation notes.

This is a **separate endpoint** from personal statements (`POST /api/v1/statements/generate`). Buddy letters are longer, written as the witness, and meant to be downloaded as a PDF or VA Form 21-10210, not pasted into VA.gov's 400-character field.

## Endpoint

```
POST {base_url}/api/v1/buddy-statements/generate
```

| Environment | `base_url` |
|-------------|----------------------|
| Staging     | `https://stage-portal.vetcomm.link` |
| Production  | `https://portal.vetcomm.org` |

Authentication, HMAC signing, and rate limits are **identical** to the personal statement API. See [lms-statement-api.md](./lms-statement-api.md).

## Request body

```json
{
  "request_id": "lms_buddy_20260825_abc123",
  "veteran_name": "Ivan Bullert",
  "condition": {
    "name": "Bilateral shoulder and lumbar strain",
    "category": "shoulder"
  },
  "witness": {
    "relationship": "buddy",
    "name": "Merle Lofgren",
    "relationship_detail": "Served with me as a 2111 armor repairman",
    "how_met": "Met in November 1972 at Aberdeen Proving Grounds attending MOS 2111 school, then served together at TBS Quantico.",
    "witnessed_event": true,
    "witnessed_impact": false
  },
  "event": {
    "when": "1973-1974",
    "where": "TBS Armory, Quantico, Virginia",
    "what": "He lifted 81mm mortar tubes, M-14s on a 15-foot pole, ammo boxes, and a 462-pound recoilless rifle daily for 12-13 months. Complained of shoulder and back pain. Never went to medical."
  },
  "impact": null,
  "service_context": {
    "branch_of_service": ["Marine Corps"],
    "mos": "2111"
  },
  "regeneration": null
}
```

### Fields

| Field | Required | Notes |
|------|----------|-------|
| `request_id` | yes | String ≤64 chars. LMS-generated; echoed in the response. |
| `veteran_name` | yes | The veteran's name as it should appear in the letter. |
| `condition.name` | yes | Free text condition this statement supports. |
| `condition.category` | yes | Same enum as personal statements. |
| `witness.relationship` | yes | `family` \| `friend` \| `buddy` \| `officer` \| `other` |
| `witness.name` | yes | The person who will sign the letter. |
| `witness.relationship_detail` | yes | In the veteran's words, e.g. "My wife of 22 years". |
| `witness.how_met` | yes | How and when they first met. Min 5 chars. |
| `witness.witnessed_event` | yes | Boolean. They were there when it happened. |
| `witness.witnessed_impact` | yes | Boolean. They have seen how it affects the veteran. |
| `event.when` / `event.where` / `event.what` | yes if `witnessed_event` | `what` min 15 chars. |
| `impact.change` | yes if `witnessed_impact` | Min 15 chars. |
| `impact.examples` | no | Concrete moments. |
| `service_context.branch_of_service` | no | Same exact strings as personal statements. |
| `service_context.mos` | no | MOS / Rate / AFSC. |
| `regeneration` | no | `null` on first attempt; object on regenerations. |

At least one of `witnessed_event` or `witnessed_impact` must be `true`. Send both `true` when the witness can speak to the incident **and** the later impact.

Grammar in the veteran's answers does not need to be clean. The generator rewrites everything into the **witness's** first-person voice.

### `witness.relationship` values

| Value | Meaning | VA Form 21-10210 checkbox |
|-------|---------|---------------------------|
| `family` | Spouse, sibling, parent, adult child | Family/Friend |
| `friend` | Long-time civilian friend | Family/Friend |
| `buddy` | Someone they served with | Served with Veteran |
| `officer` | Superior, NCO, chain of command | Served with Veteran |
| `other` | Neighbor, employer, clergy, coworker | Other (specify = relationship_detail) |

### Regeneration

Same rules as personal statements. Up to **5 attempts**. Attempt 1 has `regeneration: null`.

```json
"regeneration": {
  "previous_statement": "My name is Merle Lofgren...",
  "veteran_feedback": "Add that he also complained about his finger after catching it in a rifle rack.",
  "attempt_number": 2
}
```

`attempt_number` > 5 → `400` `regeneration_limit_exceeded`.

## Responses

### 200 Success

```json
{
  "request_id": "lms_buddy_20260825_abc123",
  "status": "success",
  "statement": "My name is Merle Lofgren. I am a veteran of the Marine Corps...",
  "character_count": 1680,
  "attempt_number": 1,
  "generated_at": "2026-08-25T21:30:28+00:00"
}
```

- `statement` — plain text body only. No heading, salutation, certification, markdown, or em dashes. Wrap it in your own PDF or VA Form 21-10210.
- `character_count` — always ≤2500; target 1400–2000.
- `attempt_number` — `1` for initial, `2`–`5` for regenerations.

### Errors

Same codes as personal statements: `insufficient_input`, `regeneration_limit_exceeded`, `generation_failed_quality`, `unauthorized`, `429`, `internal_error`.

## What LightSpeed must collect

1. Veteran name (from profile is fine).
2. Which condition this letter supports.
3. Who is writing it (relationship type + their name + relationship in the veteran's words + how they met).
4. What they can speak to: the event, the later impact, or both.
5. Event details and/or impact details, matching those checkboxes.

Warn the veteran that **nothing is stored** as a signed file. They must download/send the letter to the witness for signature, then upload the signed copy to the VA.

Recommended: at least 3 statements from at least 2 different perspectives (for example one service buddy + one spouse).

## Output quality (fixed; not configurable)

- Audience: VA rater.
- First person **from the buddy**, rewritten from the veteran's answers.
- Structure: who I am and how I know them → what I observed → why I am writing.
- Observable facts only. The witness does not diagnose.
- No invented dates, units, MOS duties, awards, or combat events.
- Character target 1400–2000; hard cap 2500.

## Data handling

Veteran input and generated statements are **not stored**. Only anonymous metadata is retained (`request_id`, timestamp, category, relationship type as `claim_path`, attempt number, status code, character count, `kind=buddy`).

## Suggested integration checks

1. Happy path (service buddy / event) → `200`, `character_count` ≤ 2500.
2. Wrong API key or bad HMAC → `401`.
3. Both witness flags false → `400` `insufficient_input`.
4. Regeneration attempt 2 with feedback → `200`, `attempt_number: 2`.
5. `attempt_number: 6` → `400` `regeneration_limit_exceeded`.
6. Family / impact-only path with no `event` object.
7. Spot-check that the statement is in the witness's voice, not the veteran's.
