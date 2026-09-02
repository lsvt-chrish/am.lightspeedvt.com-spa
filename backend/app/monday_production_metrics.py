"""
Pure metric calculation for the AI Production dashboard, per
docs/monday-api-integration-plan.md. Takes the flat item list returned by
monday_production_client.fetch_board_items and produces the four live
metrics (Up Next, Pipeline, In Progress, Hours Open).

Business-rule defaults used here (per the doc's "Still need before coding
starts" follow-up, pending confirmation with Cherrelle/Amber):
  - "Pending Approval" maps to Pipeline (not Up Next) -- the "Waiting on
    Client" naming question is unresolved but doesn't block this default.
  - "On Hold" items are excluded from all metrics entirely.
  - Dynamic Goal is a plain configured value (Option A), not calculated from
    active renderer headcount.
Any status not explicitly mapped below (prepping/new-ticket statuses,
Finished/Sent to Config, On Hold, etc.) is implicitly excluded, since it
simply doesn't match any bucket.
"""
PIPELINE_WEIGHT = 0.5

AVATAR_CREATION_GROUP_NAME = "avatar creation"

STATUS_TO_BUCKET = {
    "Assigned": "up_next",
    "Pending Approval": "pipeline",
    "Render In Progress": "in_progress",
    "Revisions In Progress": "in_progress",
    "Sample In Progress": "in_progress",
}


def _is_excluded(item: dict) -> bool:
    group_name = (item.get("group_name") or "").strip().lower()
    return group_name == AVATAR_CREATION_GROUP_NAME


def compute_metrics(items: list[dict], capacity_goal_hours: float) -> dict:
    buckets: dict[str, list[dict]] = {"up_next": [], "pipeline": [], "in_progress": []}

    for item in items:
        if _is_excluded(item):
            continue
        bucket = STATUS_TO_BUCKET.get(item.get("status"))
        if bucket is not None:
            buckets[bucket].append(item)

    up_next_hours = sum(i["hours"] for i in buckets["up_next"])
    pipeline_hours = sum(i["hours"] for i in buckets["pipeline"])
    in_progress_hours = sum(i["hours"] for i in buckets["in_progress"])
    weighted_pipeline_hours = pipeline_hours * PIPELINE_WEIGHT

    hours_open = capacity_goal_hours - in_progress_hours - up_next_hours - weighted_pipeline_hours

    return {
        "capacity": {"dynamicGoal": capacity_goal_hours, "pipelineWeight": PIPELINE_WEIGHT},
        "metrics": {
            "pipelineHours": pipeline_hours,
            "weightedPipelineHours": weighted_pipeline_hours,
            "upNextHours": up_next_hours,
            "inProgressHours": in_progress_hours,
            "hoursOpen": hours_open,
        },
        "detail": {
            "pipeline": {"hours": pipeline_hours, "weightedHours": weighted_pipeline_hours, "items": buckets["pipeline"]},
            "upNext": {"hours": up_next_hours, "items": buckets["up_next"]},
            "inProgress": {"hours": in_progress_hours, "items": buckets["in_progress"]},
        },
    }
