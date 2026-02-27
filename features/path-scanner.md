# Interactive Video Scanner (Interactive Courseware JSON)

## Overview

The Interactive Video Scanner analyzes Lightspeed VT–style interactive courseware JSON files to enumerate every path a user can take through the flow and compute how long each path takes. It supports JSON provided by URL (e.g. from S3 or courseware CDN).

After a scan, the feature reports:

- **Total duration of all segments** – Sum of duration across every segment in the file
- **Shortest path** – Minimum duration from start to any terminal
- **Longest path** – Maximum duration from start to any terminal
- **Average path** – Mean duration over all distinct paths
- **Total paths** – Number of distinct paths from entry to a terminal
- **Total segments** – Number of unique segments (video nodes) in the JSON

## User flow

1. User opens the **Interactive Video Scanner** page (e.g. `/scan`).
2. User pastes a **JSON URL** (e.g. `https://lsvt-courseware.s3.amazonaws.com/files/121/interactiveFiles/ultimate_vapor_app_screener_july_2024_b_BDF7.json`).
3. User clicks **Scan** (or **Analyze**).
4. Backend fetches the JSON, parses the graph, enumerates paths, and computes durations.
5. Results are shown: total segment duration, total segments, total paths, shortest/longest/average path duration.

## JSON format (expected)

- **Root**: `debug`, `version`, `videos` (object mapping segment id → segment).
- **Segment**:
  - `onEnd`: Optional. `loop.start` = loop point in seconds (used as segment duration). `complete: true` or `redirect` = path ends (terminal).
  - `buttons`: Optional array. Each button may have `action.nextSegment` (id of next segment).
  - `sortOrder`: Optional; used to find the entry segment (e.g. `sortOrder === 1` or key `"intro"`).
- **Entry**: The segment with `sortOrder === 1`, or key `"intro"`, or the first segment in `videos`.

## Segment duration rules

Segment duration (in seconds) is computed in this order:

1. **`onEnd.loop.start`** – If present, segment duration = this value (video plays to the loop point before the user can continue).
2. **Max of `button.time.start`** – If the segment has `buttons`, duration = maximum `time.start` among all buttons (when the last choice appears).
3. **0** – Otherwise (e.g. terminal segments with no buttons).

## Path enumeration

- **Graph**: From each segment, “next” nodes are taken from `action.nextSegment` on each button (only segment ids that exist in `videos` are used).
- **Terminals**: Segments with no outgoing edges (no buttons or no valid `nextSegment`), or with `onEnd.complete` or `onEnd.redirect`.
- **Traversal**: DFS from the entry segment to each terminal. Each path is an ordered list of segment ids; no segment is visited twice in the same path (cycles are avoided so paths are finite).
- **Path duration**: For each path, duration = sum of segment durations for every segment in that path.

## API

- **Endpoint**: `POST /api/scan/paths` (or `POST /scan/paths` depending on proxy).
- **Body**: `{ "json_url": "https://..." }`.
- **Response**: JSON with `total_segment_duration_seconds`, `total_segments`, `total_paths`, `shortest_path_seconds`, `longest_path_seconds`, `average_path_seconds`, and optional human-readable duration fields (e.g. `shortest_path_duration_display`).

Errors (invalid URL, fetch failure, missing `videos`) return 400 with a message.

## Implementation notes

- Backend uses **httpx** to fetch the JSON URL (server-side) to avoid CORS.
- Path analysis is implemented in a dedicated module (e.g. `backend/app/path_analyzer.py`); the scan API parses the JSON and calls this module.
- The scan endpoint does not require session or API credentials.

## Related files

- Backend: `backend/app/path_analyzer.py`, `backend/app/api/scan.py`
- Frontend: `frontend/src/views/PathScannerPage.vue`
- Router: route `/scan` and nav link in `App.vue`
