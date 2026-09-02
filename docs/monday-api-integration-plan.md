# AI Production Dashboard — API Data Requirements

> **Revision note:** This version has been corrected against the Aug 21 "Dashboards Meeting" transcript (Cherrelle, Amber, Chris). Changes from the prior draft are called out inline as **[CORRECTED]** or **[NEW — from transcript]**. One item (Hours Completed) has been moved out of scope pending confirmation — see the Appendix.

## Objective

Create an API request/endpoint that returns the data required to power a **live** AI Production dashboard.

**[CORRECTED]** The meeting confirmed exactly **four** live metrics — this is the confirmed scope for this build:

1. Up Next
2. Pipeline
3. In Progress
4. Hours Open

Hours Completed (a fifth, weekly-baseline metric) does not appear anywhere in this meeting and was not requested by Cherrelle. It's been moved to the Appendix as an unconfirmed, out-of-scope item rather than treated as a required deliverable.

The dashboard needs to reflect current production workload in near real time — the whole reason for building this is that the existing weekly manual snapshot goes stale the moment new work gets thrown at production mid-week.

---

# Data Source Context **[NEW — from transcript]**

- Board: **AI Production** board/team in Monday.com.
- Pre-production and pipeline-stage items (prepping, sample in progress, pending approval) live under the **"New Projects"** group on that board.
- Once an item is assigned, it moves into an **individual producer's bucket** (Kyle, Marty, Brock, freelancers, etc.) rather than a shared group — group naming is per-person from that point on.
- Because group membership varies by producer once work is assigned, **Project Status — not Group — must remain the source of truth** for categorizing an item into Pipeline / Up Next / In Progress. Groups are useful only for exclusions/debugging (e.g., confirming an item is still in "New Projects").

---

# Metric Definitions

## 1. Up Next

**Definition**

Approved hours queued and ready to render. Confirmed — no longer dependent on client approval.

**Monday mapping**

Primary status: `Assigned`

Confirmed multiple times in the meeting — e.g., Amber: *"Up next would only be assigned."* Assigned hours can sit for as little as 5–10 minutes before a producer picks them up, which is exactly why this needs to be live rather than a weekly snapshot.

**API calculation**

```text
Up Next Hours = SUM(Hours WHERE Project Status = Assigned)
```

**Required API fields**

* Item / Project ID
* Project Status
* Hours
* Group or production bucket
* Last Updated timestamp

---

## 2. Pipeline

**Definition**

Hours tied to samples that have already been prepped and sent to the client, and are now awaiting client approval. Not guaranteed to enter production, so only counted at **50%** in the Hours Open calculation.

**Monday mapping**

Primary status: `Pending Approval`

This was stated and re-confirmed several separate times in the meeting (e.g., *"the hour is tied to samples still waiting on client approval"* / *"pending approval maps to pending samples"*).

**[NEW — from transcript] Open question / contradiction to resolve:** Late in the call, Amber momentarily suggested "Pending Approval" or a "Waiting on Client" status should count toward **Up Next** instead of Pipeline, before the group returned to status-based mapping without fully re-confirming which status name is correct. Since this directly conflicts with the Pipeline definition used everywhere else in the call, **confirm with Cherrelle/Amber before implementation** whether "Waiting on Client" is:
- (a) just another name for `Pending Approval` (no conflict), or
- (b) a separate status that should actually map to Up Next.

**API calculation**

```text
Pipeline Hours = SUM(Hours WHERE Project Status = Pending Approval)
Weighted Pipeline Hours = Pipeline Hours × 0.50
```

Pipeline is returned as the **full number of hours** for display; the 50% weighting only applies inside the Hours Open calculation.

**The team explicitly decided to track hours, not sample/ticket counts** — Cherrelle: *"we can send a bunch of samples out, but if the client has five hours that we have to deliver on... the number that makes the most sense is the hours."*

**Required API fields**

* Item / Project ID
* Project Status
* Hours
* Group
* Client/project identifier
* Last Updated timestamp

---

## 3. In Progress

**Definition**

Hours of render work currently being actively worked on.

**Monday mappings**

```text
Render In Progress
Revisions In Progress
Sample In Progress
```

Confirmed directly: Cherrelle — *"these two revisions in progress or render in progress, this should actually count for the in progress snapshot."* Amber added Sample In Progress: *"he's technically in progress working."*

**API calculation**

```text
In Progress Hours =
SUM(
    Hours
    WHERE Project Status IN (
        "Render In Progress",
        "Revisions In Progress",
        "Sample In Progress"
    )
)
```

**Required API fields**

* Item / Project ID
* Project Status
* Hours
* Assigned producer
* Group
* Last Updated timestamp

---

## 4. Hours Open

**Definition**

Remaining production capacity after subtracting In Progress, Up Next, and 50% of Pipeline. Allowed to go negative when production is overcommitted — Cherrelle gave this exact scenario: *"I can tell Brad and Jason that we had eight hours open in the beginning of the week, but now they've thrown 20 more hours to us and we no longer have that eight and a half hours open."* That's the core reason this needs to be live instead of a weekly manual number.

**Formula**

```text
Hours Open =
Dynamic Goal
- In Progress
- Up Next
- (Pipeline × 0.50)
```

Example:

```text
Dynamic Goal:   20
In Progress:     4
Up Next:         3
Pipeline:         6

Weighted Pipeline: 6 × 0.50 = 3
Hours Open: 20 - 4 - 3 - 3 = 10
```

Overcommitted example:

```text
Dynamic Goal:   20
In Progress:    12
Up Next:         8
Pipeline:         4

Hours Open = 20 - 12 - 8 - 2 = -2
```

The API should return `hoursOpen: -2` rather than clamping to zero.

---

## 5. Dynamic Goal / Current Capacity

Current capacity: **20 hours**, confirmed by Cherrelle to correspond to the current **4 renderers**, and expected to change: *"we're expected to have six eventually. So we'll need to update that once we hire the two additional renders that we're interviewing."*

Because of this, the capacity used for Hours Open should **not** be permanently hardcoded.

### Option A — Return the configured capacity
```json
{ "capacityGoal": 20 }
```

### Option B — Calculate from active renderer count
```text
Dynamic Goal = Active Renderer Count × Capacity Per Renderer
```
With the current rule (4 renderers = 20 hours → 5 hours/renderer), 6 active renderers → 30 hours. This lines up with how the team already talks about capacity in terms of headcount, but which approach to actually implement (configured value vs. calculated) should still be confirmed with the business team — it wasn't explicitly decided in this meeting, only the underlying 4-renderers-to-6-renderers change was.

---

# Exclusions **[NEW — from transcript]**

These came up explicitly in the meeting and were not previously captured:

1. **Prepping / script-writing work is excluded from all three metrics.** When Amber asked directly whether her prepping (writing the script and outline before a sample is even made) should count as In Progress, Cherrelle answered plainly: *"No, that's just before."* Prepping happens upstream of Pipeline entirely — it shouldn't be counted anywhere in Up Next, Pipeline, or In Progress.
2. **Avatar Creation section items are excluded.** Amber described this as a catch-all for one-off avatar requests that aren't tied to any project or course credits — not real workload. These should not contribute to any of the four metrics.
3. **"On Hold" status is ambiguous and needs confirmation.** Amber indicated some on-hold items still count toward Pipeline (e.g., a sample on hold waiting on an avatar render finishing) while at least one other on-hold item she flagged (blocked on the client providing scripts) was called out as "not really" belonging in Pipeline in the moment. There isn't a clean, consistent rule from the transcript for on-hold items — **needs an explicit business rule before implementation.**
4. Completed/downstream items (`Sent to Config`, `Finished`, etc.) should no longer contribute to any of the four live metrics — this was implicit in the flow described (assigned → in progress → done) rather than stated as a rule, but it follows directly from the workflow the team described.

---

# Status-to-Metric Mapping

| Monday Project Status    | API Metric                             | Confidence |
| ------------------------ | --------------------------------------- | ---------- |
| `Pending Approval`       | Pipeline                                | Confirmed repeatedly, but see the Up Next open question above |
| `Assigned`               | Up Next                                 | Confirmed |
| `Render In Progress`     | In Progress                             | Confirmed |
| `Revisions In Progress`  | In Progress                             | Confirmed |
| `Sample In Progress`     | In Progress                             | Confirmed |
| Prepping / new ticket    | Excluded from all metrics               | Confirmed |
| Avatar Creation items    | Excluded from all metrics               | Confirmed |
| On Hold                  | Unclear — needs a rule                  | **Unresolved** |
| Finished/downstream work | Excluded from current workload metrics  | Inferred from workflow |

Items should be categorized primarily by **Project Status**, not Group — Group is used only for exclusions/context (e.g., confirming an item is in "New Projects").

---

# Business Rules

1. Hours, not project/sample counts, drive all workload metrics.
2. `Pending Approval` hours belong to Pipeline — **pending confirmation of the "Waiting on Client" naming question above.**
3. Pipeline displays its full hours but contributes only 50% to Hours Open.
4. `Assigned` hours belong to Up Next.
5. Render/Revisions/Sample In Progress belong to In Progress.
6. In Progress and Up Next count at 100% against capacity.
7. Hours Open may be negative.
8. The Hours Open capacity goal is dynamic/configurable (confirmed: tied to renderer headcount, currently 4, moving to 6).
9. Prepping/script-writing work and Avatar Creation items are excluded from all three workload buckets.
10. On Hold status handling is unresolved and needs an explicit rule before go-live.
11. Completed/downstream items no longer contribute to Pipeline, Up Next, or In Progress.

---

# Calculation Summary

```text
Pipeline =
SUM(Pending Approval Hours)

Weighted Pipeline =
Pipeline × 0.50

Up Next =
SUM(Assigned Hours)

In Progress =
SUM(Render In Progress + Revisions In Progress + Sample In Progress)

Hours Open =
Dynamic Goal - In Progress - Up Next - Weighted Pipeline
```

---

# Required Source Data

| Field               | Purpose                                              |
| ------------------- | ----------------------------------------------------- |
| `itemId`            | Unique production/project identifier                  |
| `projectName`       | Human-readable project reference                       |
| `projectStatus`     | Determines Pipeline, Up Next, or In Progress           |
| `hours`             | Number of render-content hours                         |
| `groupId`/`groupName` | Used for exclusions/debugging (New Projects, per-producer buckets, Avatar Creation) |
| `assignedProducer`  | Producer responsible for the work                      |
| `updatedAt`         | Freshness validation                                    |

---

# Recommended API Response

```json
{
  "generatedAt": "2026-09-01T15:30:00-05:00",
  "capacity": {
    "dynamicGoal": 20,
    "pipelineWeight": 0.5
  },
  "metrics": {
    "pipelineHours": 4.5,
    "weightedPipelineHours": 2.25,
    "upNextHours": 3,
    "inProgressHours": 5,
    "hoursOpen": 9.75
  }
}
```

# Recommended Detailed Response (for drill-down/debugging)

```json
{
  "metrics": {
    "pipeline": {
      "hours": 4.5,
      "weightedHours": 2.25,
      "items": [
        { "itemId": "12345", "projectName": "Client A", "projectStatus": "Pending Approval", "hours": 2.5 },
        { "itemId": "67890", "projectName": "Client B", "projectStatus": "Pending Approval", "hours": 2 }
      ]
    },
    "upNext": { "hours": 3, "items": [] },
    "inProgress": { "hours": 5, "items": [] }
  }
}
```

---

# API Request Recommendation

```text
GET /api/production/dashboard
```

Since Hours Completed is out of scope for this build (see Appendix), there's no need for a reporting-period query parameter for now — the endpoint can simply reflect current live state on every call.

---

# Open Questions for Development

1. **"Waiting on Client" vs. "Pending Approval"** — is this the same status under a different name, or a separate status that should map to Up Next instead of Pipeline? (Direct conflict in the transcript — see Pipeline section.)
2. **On Hold status** — which on-hold cases (if any) should count toward Pipeline vs. be excluded entirely?
3. **Dynamic Goal sourcing** — configured value (Option A) vs. calculated from active renderer count (Option B)? Not explicitly decided, only that it needs to move from 20→30 hours once the two renderer hires land.
4. Are there any additional statuses beyond the three listed that should count as In Progress?
5. Are there any additional statuses equivalent to Pending Approval or Assigned?
6. How should deleted, archived, or canceled projects be handled? (Recommend excluding from all metrics — not discussed directly in this meeting.)
7. Should the "collaboration" section (multi-person items, whose status changes infrequently per Amber) need special handling, or is status-based tracking sufficient there too?

---

# Acceptance Criteria

The API is complete when the dashboard can retrieve, from one response:

```text
Up Next Hours
Pipeline Hours
In Progress Hours
Hours Open
Dynamic Capacity Goal
```

and the following is reproducible:

```text
Hours Open = Dynamic Goal - In Progress - Up Next - (Pipeline × 50%)
```

The response should update whenever underlying project status, hours, or configured capacity changes. This is meant to replace Amber/Cherrelle's manual weekly tracking with a single live source of truth that both Production and Solutions can reference directly in Monday.

---

# Appendix: Hours Completed — Not Confirmed in This Meeting

The prior draft of this doc included a fifth metric, "Hours Completed," measured against a fixed 20-hour weekly baseline, with its own `productionCompletedAt` field requirement. **None of this appears in the Aug 21 transcript** — Cherrelle's ask was specifically for the four live metrics above, and there's no mention of a completed-hours tracker, a fixed baseline, or a completion timestamp anywhere in the call.

This isn't necessarily wrong as a future feature, but it shouldn't be treated as confirmed scope or baked into acceptance criteria until it's actually discussed with Cherrelle. If it does move forward, the original open questions still apply:

- What field/timestamp represents actual production completion (none currently confirmed to exist)?
- Can Hours change after completion?
- What's the official start/end of a production week?
- Does Hours Completed include revisions/samples, or only final AI render content?

---

# Implementation Plan (Phase 1)

Phase 1 builds exactly this doc's spec: one board, four fixed metrics, hard-coded status
mapping. The generic admin-configurable multi-board/multi-column system discussed separately is
deferred to Phase 2, once this ships and the board list actually needs to grow.

## Decisions locked in for Phase 1

- Board: `18405675239` (confirm this is in fact the "AI Production" board named in this doc).
- Unresolved business rules (naming conflict, On Hold, Dynamic Goal sourcing) use this doc's
  stated defaults: `Pending Approval` → Pipeline, On Hold excluded from all metrics, Dynamic
  Goal as a configured value (Option A). Flagged as follow-ups to confirm with Cherrelle/Amber,
  not blockers.
- Auth: Monday API token stored as env var `MONDAY_API_TOKEN` (added directly to `.env`/secrets,
  never pasted in chat).
- No scheduler exists in this codebase yet — adding **APScheduler**, in-process, for the
  15-minute poll. Single-instance assumption; flagged as a future concern if the app ever runs
  multiple replicas.

## Codebase fit (matches existing conventions)

The existing Monday integration is inbound-only (webhook → `MondayEvent`/`MondayBoard`, no
outbound API key, no GraphQL client anywhere yet). This phase adds the first outbound GraphQL
client, following the `vetcomm_api.py` pattern already used for other third-party integrations:
module-level async functions, a per-call `httpx.AsyncClient`, a custom `<Name>Error` exception,
config pulled from `core/config.py` as constants.

### Config (`backend/app/core/config.py`)
```python
monday_api_token: str = ""
monday_api_url: str = "https://api.monday.com/v2"
monday_production_board_id: str = "18405675239"
```

### GraphQL client (`backend/app/monday_production_client.py`)
- `fetch_board_items(board_id, column_ids) -> list[dict]` — queries `items_page` for the board,
  requesting only `Project Status`, `Hours`, `Group`, `Assigned Producer`, `Last Updated`, item
  id/name. Paginates via cursor.
- `MondayProductionApiError` exception carrying status/GraphQL error details.
- Backs off / retries on `COMPLEXITY_BUDGET_EXHAUSTED` / `RATE_LIMIT_EXCEEDED` error codes.

### Metric calculation (`backend/app/monday_production_metrics.py`)
- Pure functions implementing the status-to-metric mapping and formulas from this doc:
  `compute_metrics(items, capacity_goal) -> dict` producing the summary shape in "Recommended
  API Response", plus the per-item drill-down shape.
- Excludes: prepping/new-ticket status, Avatar Creation group items, On Hold (per default above),
  Finished/downstream statuses.

### Storage
- `MondayProductionSnapshot` — one row per refresh (or per item — TBD once column IDs for the
  board are confirmed), `fetched_at`, raw + computed metrics, so both the 15-min job and the
  on-demand refresh write to the same place the endpoint reads from. Alembic migration.
- Dynamic Goal / capacity stored as a simple configured value (Option A), editable via one small
  admin field (not the full Phase-2 admin page) — e.g. a single settings row or env var, TBD.

### Refresh (scheduled + on-demand)
- `backend/app/monday_production_refresh.py`: `refresh_production_snapshot()` — pulls, computes
  metrics, upserts the snapshot.
- APScheduler job in `main.py` startup, every 15 minutes.
- `POST /api/monday/production/refresh` triggers the same function on demand (for the UI's
  "Refresh" button).

### API routes (`backend/app/api/monday_production.py`)
- `GET /api/production/dashboard` — per this doc's spec, returns the summary + optionally the
  detailed drill-down (query param, e.g. `?detail=true`).
- `POST /api/monday/production/refresh` — on-demand pull, admin-gated like the rest of the
  Monday admin surface (`Depends(require_admin)`), consistent with `monday_boards.py`.
- Registered in `main.py` alongside the existing Monday routers.

### Frontend
- A "Refresh" button wherever this dashboard is displayed (new page, or an existing dashboard
  view — need to confirm which), calling `POST /api/monday/production/refresh` with
  `fetch(..., { credentials: 'include' })`, matching the existing admin-page conventions.
- Full admin config UI (board list, column picker, status mapping editor) is Phase 2.

## Still need before coding starts

1. Confirm board `18405675239` is the "AI Production" board this doc describes.
  - Yes, this is correct.
2. Exact column IDs on that board for: Project Status, Hours, Group, Assigned Producer, Last
   Updated timestamp (can enumerate via the API once the token is in place).
   Project Status = color_mm1t3z1j
   Hours = numeric_mm57p53w
   Group = group_mm1th225
   Assigned Producer = multiple_person_mm1tp0k0
   Last Updated = None
3. Where should this dashboard live in the frontend — new page, or added to the existing ops
   dashboard?
   - Add to exiting ops page
4. Confirm the 3 unresolved business rules with Cherrelle/Amber (tracked as follow-ups, not
   blockers per your answer above).