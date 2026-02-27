"""Analyze Lightspeed VT–style interactive courseware JSON: enumerate paths and compute durations."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx


def _format_duration(seconds: float) -> str:
    """Format seconds as MM:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _get_entry_segment_id(videos: dict[str, Any]) -> str | None:
    """Resolve entry segment: sortOrder 1, or 'intro', or first key."""
    if not videos:
        return None
    by_sort = next((sid for sid, seg in videos.items() if seg.get("sortOrder") == 1), None)
    if by_sort:
        return by_sort
    if "intro" in videos:
        return "intro"
    return next(iter(videos))


# EXTINF duration line: #EXTINF:10.5, or #EXTINF:10.5,title
_EXTINF_RE = re.compile(r"#EXTINF:([\d.]+)")


async def _fetch_m3u8_duration(client: httpx.AsyncClient, url: str) -> float:
    """
    Fetch an m3u8 playlist URL and return total duration in seconds.
    If master playlist, follow first variant. On failure return 0.0.
    """
    try:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return 0.0
    base = url.rsplit("/", 1)[0] + "/" if "/" in url else url
    lines = [ln.strip() for ln in text.splitlines()]
    # Master playlist: has EXT-X-STREAM-INF; first variant is next non-tag line
    if any("#EXT-X-STREAM-INF" in ln for ln in lines):
        for i, ln in enumerate(lines):
            if "#EXT-X-STREAM-INF" in ln and i + 1 < len(lines):
                variant = lines[i + 1].strip()
                if variant and not variant.startswith("#"):
                    variant_url = urljoin(url, variant)
                    return await _fetch_m3u8_duration(client, variant_url)
        return 0.0
    total = 0.0
    for ln in lines:
        m = _EXTINF_RE.search(ln)
        if m:
            try:
                total += float(m.group(1))
            except (TypeError, ValueError):
                pass
    return total


async def fetch_segment_durations(
    videos: dict[str, Any],
    client: httpx.AsyncClient,
) -> dict[str, float]:
    """
    Fetch real duration for each segment that has a 'src' URL (m3u8).
    Returns dict segment_id -> duration_seconds. Same src URL is only fetched once.
    """
    url_to_duration: dict[str, float] = {}
    durations: dict[str, float] = {}
    for seg_id, seg in videos.items():
        src = seg.get("src") if isinstance(seg, dict) else None
        if not src or not isinstance(src, str):
            durations[seg_id] = _segment_duration(seg)
            continue
        if src not in url_to_duration:
            url_to_duration[src] = await _fetch_m3u8_duration(client, src)
        durations[seg_id] = url_to_duration[src]
    return durations


def _segment_duration(seg: dict[str, Any]) -> float:
    """Segment duration in seconds: onEnd.loop.start, else max(button.time.start), else 0."""
    on_end = seg.get("onEnd") or {}
    if isinstance(on_end, dict) and "loop" in on_end:
        loop = on_end["loop"]
        if isinstance(loop, dict) and "start" in loop:
            try:
                return float(loop["start"])
            except (TypeError, ValueError):
                pass
    buttons = seg.get("buttons")
    if isinstance(buttons, list) and buttons:
        max_start = 0.0
        for b in buttons:
            if not isinstance(b, dict):
                continue
            t = b.get("time")
            if isinstance(t, dict) and "start" in t:
                try:
                    max_start = max(max_start, float(t["start"]))
                except (TypeError, ValueError):
                    pass
        return max_start
    return 0.0


def _is_terminal(seg: dict[str, Any], next_ids: list[str]) -> bool:
    """True if segment has no outgoing edges or has onEnd.complete/redirect."""
    if next_ids:
        return False
    on_end = seg.get("onEnd") or {}
    if not isinstance(on_end, dict):
        return True
    return "complete" in on_end or "redirect" in on_end


def _build_graph(videos: dict[str, Any]) -> dict[str, list[str]]:
    """Map segment id -> list of unique next segment ids (one edge per destination, not per button)."""
    graph: dict[str, list[str]] = {}
    valid_ids = set(videos)
    for seg_id, seg in videos.items():
        next_ids_set: set[str] = set()
        buttons = seg.get("buttons")
        if isinstance(buttons, list):
            for b in buttons:
                if not isinstance(b, dict):
                    continue
                action = b.get("action")
                if isinstance(action, dict):
                    nxt = action.get("nextSegment")
                    if nxt in valid_ids:
                        next_ids_set.add(nxt)
        graph[seg_id] = list(next_ids_set)
    return graph


def _enumerate_paths(
    entry_id: str,
    graph: dict[str, list[str]],
    videos: dict[str, Any],
) -> list[list[str]]:
    """DFS from entry to terminals; each path is list of segment ids (no cycles)."""
    paths: list[list[str]] = []

    def dfs(seg_id: str, path: list[str], visited: set[str]) -> None:
        if seg_id in visited:
            return
        visited.add(seg_id)
        path.append(seg_id)
        next_ids = graph.get(seg_id, [])
        seg = videos.get(seg_id, {})
        if _is_terminal(seg, next_ids) or not next_ids:
            paths.append(path[:])
        else:
            for nxt in next_ids:
                dfs(nxt, path, visited)
        path.pop()
        visited.discard(seg_id)

    dfs(entry_id, [], set())
    return paths


def analyze(
    data: dict[str, Any],
    durations_override: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Analyze courseware JSON. Expects top-level 'videos' object (segmentId -> segment).
    If durations_override is provided (e.g. from fetch_segment_durations), those
    real segment durations are used; otherwise durations come from JSON (loop/button times).
    Returns stats: total_segment_duration_seconds, total_segments, total_paths,
    shortest/longest/average path (seconds + _display), and optional paths list.
    """
    videos = data.get("videos")
    if not isinstance(videos, dict):
        return {
            "error": "Missing or invalid 'videos' in JSON",
            "total_segments": 0,
            "total_paths": 0,
            "total_segment_duration_seconds": 0,
            "shortest_path_seconds": 0,
            "longest_path_seconds": 0,
            "average_path_seconds": 0,
            "shortest_path_duration_display": "0:00",
            "longest_path_duration_display": "0:00",
            "average_path_duration_display": "0:00",
            "paths": [],
        }

    # Segment durations: use real (m3u8) when provided, else JSON-based
    if durations_override is not None:
        durations = {sid: durations_override.get(sid, _segment_duration(seg)) for sid, seg in videos.items()}
    else:
        durations = {sid: _segment_duration(seg) for sid, seg in videos.items()}
    graph = _build_graph(videos)
    entry_id = _get_entry_segment_id(videos)
    if not entry_id:
        return {
            "error": "Could not determine entry segment",
            "total_segments": len(videos),
            "total_paths": 0,
            "total_segment_duration_seconds": sum(durations.values()),
            "shortest_path_seconds": 0,
            "longest_path_seconds": 0,
            "average_path_seconds": 0,
            "shortest_path_duration_display": "0:00",
            "longest_path_duration_display": "0:00",
            "average_path_duration_display": "0:00",
            "paths": [],
        }

    paths = _enumerate_paths(entry_id, graph, videos)
    path_durations = [sum(durations[sid] for sid in p) for p in paths]

    total_segment_duration = sum(durations.values())
    total_paths = len(paths)
    if path_durations:
        shortest = min(path_durations)
        longest = max(path_durations)
        average = sum(path_durations) / len(path_durations)
    else:
        shortest = longest = average = 0.0

    def _terminal_type(segment_ids: list[str]) -> str:
        """Return 'complete' or 'redirect' from the path's last segment."""
        if not segment_ids:
            return "redirect"
        last_seg = videos.get(segment_ids[-1], {})
        on_end = last_seg.get("onEnd") or {}
        if isinstance(on_end, dict) and "complete" in on_end:
            return "complete"
        return "redirect"

    path_list = [
        {
            "segment_ids": p,
            "duration_seconds": sum(durations[sid] for sid in p),
            "terminal_type": _terminal_type(p),
        }
        for p in paths
    ]
    # Sort by duration ascending so Path 1 = shortest, last path = longest
    path_list.sort(key=lambda x: x["duration_seconds"])

    return {
        "total_segment_duration_seconds": total_segment_duration,
        "total_segments": len(videos),
        "total_paths": total_paths,
        "shortest_path_seconds": shortest,
        "longest_path_seconds": longest,
        "average_path_seconds": average,
        "shortest_path_duration_display": _format_duration(shortest),
        "longest_path_duration_display": _format_duration(longest),
        "average_path_duration_display": _format_duration(average),
        "paths": path_list,
    }
