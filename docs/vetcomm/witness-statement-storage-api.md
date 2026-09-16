# Witness (buddy) statement storage API

How the buddy statement generator saves and restores statements. This is the
**storage** service, not the generation service -- keep the two apart:

| Service | Base URL | Purpose |
| --- | --- | --- |
| Generation | `portal.vetcomm.org` | Drafts the statement text. Stores nothing. See [vetcomm-buddy-statement-api.md](vetcomm-buddy-statement-api.md). |
| Storage | `vetcomm-statements-api-production.lsvt.workers.dev` | Saves drafts so a veteran can resume. This doc. |

Staging is `vetcomm-statements-api-staging.lsvt.workers.dev`; the app picks
by `APP_ENV`. Client: `backend/app/vetcomm_statements_api.py`.

Personal statements use `/v1/statements` on the same service. The witness
routes mirror them, with the differences called out below.

---

## Endpoints

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/v1/witness-statements` | ingest token + `Idempotency-Key` |
| GET | `/v1/witness-statements/{user_id}` | read token |

---

## POST /v1/witness-statements

The app sends this exact shape. Ten top-level fields; the tenth (`request`)
is an opaque JSON blob the storage service does not need to look inside.

```json
{
  "user_id": "104882",
  "statement": "I served with Marcus Hale in the 2nd Battalion...",
  "generated_at": "2026-09-10T15:42:11.318000+00:00",
  "condition_name": "Lower back strain",
  "condition_category": "musculoskeletal",
  "witness_name": "Daniel Ortiz",
  "witness_relationship": "buddy",
  "attempt_number": 2,
  "character_count": 1847,
  "request": { "...": "see Stored payload below" }
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `user_id` | string | LSVT user id, read from the `LSVT_GUSERID` cookie |
| `statement` | text | Typically 1,500-2,000 chars. The page hard-caps at 2,500 |
| `generated_at` | timestamp | ISO 8601 UTC. Pydantic normalizes a trailing `Z` to `+00:00` |
| `condition_name` | string | Free text |
| `condition_category` | string | Same category enum as personal statements |
| `witness_name` | string | |
| `witness_relationship` | string | `family` \| `friend` \| `buddy` \| `officer` \| `other` |
| `attempt_number` | integer | 1-5 |
| `character_count` | integer | Length of `statement` |
| `request` | JSON | Full generate request, stored in the record's `payload` |

`witness_name` and `witness_relationship` are hoisted out of
`request.witness` into their own columns so a record can be identified
without unpacking the blob. Personal statements have no equivalent, because
a veteran has only one of those at a time.

### Idempotency

```
Idempotency-Key: user-{user_id}-buddy-{sha256(witness_name)[:12]}-attempt-{n}-{sha256(statement)[:16]}
```

A retried "Save" on an unchanged statement must not create a second record.
The witness hash has to be in the key: a veteran writes up to 5 statements
at once, so keying on user + attempt alone would collide across witnesses.
Witness name is lowercased and stripped before hashing.

Built in `save_buddy_statement()` in `backend/app/api/vetcomm.py`.

### Stored payload

Everything beyond the first-class fields lands in the record's `payload`,
including `request` -- the verbatim body sent to the generation API. Storing
it means the whole interaction is retrievable, and the form can be rebuilt
field-for-field on resume rather than restoring bare text.

```json
{
  "veteran_name": "Marcus Hale",
  "condition": { "name": "Lower back strain", "category": "musculoskeletal" },
  "witness": {
    "relationship": "buddy",
    "name": "Daniel Ortiz",
    "relationship_detail": "Served together in 2nd Battalion, 1st Marines",
    "how_met": "We met at Camp Pendleton in 2009 during pre-deployment training.",
    "witnessed_event": true,
    "witnessed_impact": true
  },
  "event": {
    "when": "March 2011",
    "where": "Outside Marjah, Helmand Province, Afghanistan",
    "what": "His vehicle struck an IED. I was ten feet away and helped pull him out."
  },
  "impact": {
    "change": "He could not carry his own pack for the rest of the deployment.",
    "examples": "He stopped playing basketball with us and slept sitting upright."
  },
  "service_context": { "branch_of_service": ["Marine Corps"], "mos": "0311 Rifleman" },
  "regeneration": {
    "previous_statement": "...attempt 1 text...",
    "veteran_feedback": "Add that he could not carry his own pack afterwards.",
    "attempt_number": 2
  }
}
```

`event` is `null` unless `witness.witnessed_event` is true; `impact` is
`null` unless `witness.witnessed_impact` is true; at least one must be true.
`regeneration` is `null` on a first attempt, and otherwise embeds the full
previous draft -- so a late-attempt payload carries roughly two statements'
worth of text. Still far inside the service's 512 KB body cap, which the
client also enforces up front.

---

## GET /v1/witness-statements/{user_id}

Returns **every** saved statement for the veteran, not just the latest --
buddy statements are written as a batch of up to 5, one block per witness.
There is no `?latest=true` shortcut, unlike personal statements.

The app expects the same envelope as `/v1/statements`, with `data` as an
array:

```json
{
  "user_id": "104882",
  "total": 2,
  "data": [
    {
      "statement": "...",
      "character_count": 1847,
      "attempt_number": 2,
      "generated_at": "2026-09-10T15:42:11.318Z",
      "payload": { "request": { "...": "as above" } }
    }
  ]
}
```

Verified against production: a saved statement reloads into a filled-in
block.

Worth knowing if this shape ever changes: the failure is silent.
`get_saved_buddy_statements()` in `backend/app/api/vetcomm.py` skips any
record it cannot find `payload.request` under -- built to tolerate one
malformed row, but a changed envelope makes it discard *every* row. The page
then opens with a blank block, no error, and the veteran's saved work looks
gone. Re-check by saving a statement and reloading the page.

A veteran with nothing saved should get an empty `data` array, or `404`
with `code: "not_found"` -- the app treats both as "nothing to resume" and
falls through to a blank form rather than erroring.

---

## Errors

Same envelope as the rest of the service:

```json
{ "error": { "code": "...", "message": "...", "details": { "issues": [] } } }
```

`400 bad_request`/`invalid_json`, `401 unauthorized`, `404 not_found`,
`405 method_not_allowed`, `413 payload_too_large`, `422 validation_failed`,
`500 internal_error`.
