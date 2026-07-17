# Monday.com Ops Dashboard Integration — Plan

## Background

Management currently tracks department ticket volume (Production, Client Care, Config,
Solutions Architect, Project Managers, Billing/Accounting) in a manually-populated,
self-built HTML dashboard. It's error-prone (data resets when editing line items) and
fully dependent on leads manually counting and entering numbers every week during a
recurring Monday 11:30 meeting.

All department ticket boards (except Billing/Accounting, which isn't on Monday.com)
already live in Monday.com, tracked via board groups (e.g. "Open Tasks", "Awaiting
Response", "Closed") and/or status columns (e.g. "Unread", "Working on it", "Done").

## Goal

Replace manual counting with an automated, historical event log fed by Monday.com
webhooks, so management can:

1. See current open/new/pending/closed counts per department without anyone counting.
2. Build a week-over-week and month-over-month trend per department/metric.
3. Establish a data-backed capacity baseline per role (e.g. "QC handles ~20 hrs/week"),
   so hiring requests can cite a threshold being exceeded instead of a gut feeling.
4. Eventually unify Monday-sourced departments and manually-entered Billing/Accounting
   into one ops pulse-check dashboard.

The event log is the primary artifact — current counts and trend charts are derived
views over it. This matters because cycle-time analysis (how long an item sits in
"pending" before closing) is itself a capacity signal, not just point-in-time counts.

Monday.com webhooks only report *changes*, so history starts accumulating from go-live
forward — no backfill of items that existed before the integration launched (confirmed
acceptable).

## Scope — Phase 1

Solutions Architect, Client Care, Config boards (Monday.com-native, webhook-driven).
Production and Project Manager boards are Phase 2 (they already have Monday dashboards
Chris still needs to inventory). Billing/Accounting stays manual-entry indefinitely
since it isn't on Monday.com.

## Architecture

### 1. Webhook ingestion endpoint

`POST /api/monday/webhook` (backend/app/api/monday_webhook.py — new file, unauthenticated
route since Monday.com calls it directly, not through the session-cookie auth used
elsewhere in the app).

Two payload shapes to handle:

- **Challenge handshake**: on webhook registration, Monday.com POSTs
  `{"challenge": "..."}` — echo it back verbatim, no DB write.
- **Event payload**: `item created` and `status changed` events, each carrying
  `pulseId`/`itemId`, `boardId`, `columnId` (for status changes), old/new value, and a
  timestamp.

Verify the payload is genuinely from Monday.com before writing to the DB — using
whichever mechanism Monday.com's current webhook API exposes (signing secret / static
verification token in the URL). Needs confirming against current Monday.com API docs
before implementation.

### 2. Database layer

`backend/app/db/` is currently empty (only stale `.pyc` cache remains) — rebuilding it
is a prerequisite regardless of ingestion method.

- `engine.py` / `session.py`: SQLAlchemy async engine + session, using
  `Config.database_url` (already defined in `core/config.py`, currently unused).
- `models.py`:
  - `monday_board` — board_id, name, department, group/status → bucket mapping config
    (per board, since group/status naming isn't uniform across boards).
  - `monday_event` — append-only log: `item_id`, `board_id`, `department`, `event_type`
    (created / status_changed), `old_value`, `new_value`, `occurred_at`, `raw_payload`
    (JSON, for replay/debugging).
- Migration tool: Alembic (standard pairing with SQLAlchemy, not currently in
  `pyproject.toml` — needs adding).

### 3. Board → bucket mapping

Per-board config (DB table, editable without redeploy) mapping each board's actual
group/status names to the four canonical buckets: **open, new, pending, closed**.
Confirmed from the SA Tasks board export that group names (`Open Tasks`, `Awaiting
Response`, `Closed`) map directly to buckets, with the Status column providing
finer-grained state within a group. Client Care and Config board group/status names
still need to be confirmed (via export or API) before their mappings can be written —
do not assume uniformity across boards.

### 4. Derived views / API routes

`backend/app/api/ops_dashboard.py` (new):

- Current counts per department/bucket (query: latest event per item, grouped by
  current bucket).
- Weekly/monthly trend series per department/metric (query: events bucketed by week).
- Cycle-time metric: time between an item's "pending"/"in progress" event and its
  "closed" event, per department — feeds the capacity-baseline goal.

### 5. Frontend

New Vue view, `frontend/src/views/OpsDashboardPage.vue`, using a lightweight charting
library (recommend Chart.js via vue-chartjs — nothing currently in the frontend
handles charts). Trend line per department/metric, plus a simple capacity indicator
once baseline thresholds are set manually by management (no auto-thresholding in Phase 1).

Billing/Accounting keeps a manual-entry form (existing pattern from management's original
dashboard) feeding the same `monday_event`-shaped table so it can appear in the same
unified view later, flagged as manually-sourced.

## Open items to confirm before/during implementation

- Monday.com webhook signature/verification mechanism (check current API docs).
- Client Care and Config board group/status naming (export or API pull needed).
- Whether "new" should key off item-created events specifically, or first-time-seen
  in a group (matters if items can be created directly into a non-"Open" group).
- Alembic addition to `pyproject.toml` and initial migration setup.

## Out of scope (this phase)

- Production and PM board integration (Phase 2).
- Auto-generated capacity thresholds (manual for now — management sets baselines once trend
  data exists).
- Backfilling event history prior to webhook go-live.
