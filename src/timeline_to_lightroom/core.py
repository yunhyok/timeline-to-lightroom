from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .models import ParseResult, TrackPoint


class TimelineError(ValueError):
    pass


def parse_timestamp(value: Any, fallback_timezone: ZoneInfo) -> datetime:
    if value is None:
        raise TimelineError("Missing timestamp")
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        number = int(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, UTC)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TimelineError(f"Invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=fallback_timezone)
    return parsed.astimezone(UTC)


def parse_latlng(value: Any) -> tuple[float, float]:
    if isinstance(value, str):
        text = value.strip().replace("°", "").replace(",", " ")
        parts = text.split()
        if len(parts) == 2:
            return _validate_coordinates(float(parts[0]), float(parts[1]))
    if isinstance(value, dict):
        lat = value.get("latitude", value.get("lat"))
        lon = value.get("longitude", value.get("lng", value.get("lon")))
        if lat is not None and lon is not None:
            return _validate_coordinates(float(lat), float(lon))
    raise TimelineError(f"Invalid coordinate: {value}")


def _validate_coordinates(latitude: float, longitude: float) -> tuple[float, float]:
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        raise TimelineError("Non-finite coordinate")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise TimelineError("Coordinate out of range")
    return latitude, longitude


def _point(
    time: Any,
    coordinate: Any,
    timezone: ZoneInfo,
    altitude: Any = None,
    segment: int = 0,
) -> TrackPoint:
    lat, lon = parse_latlng(coordinate)
    ele = None
    if altitude is not None:
        try:
            ele = float(altitude)
            if not math.isfinite(ele):
                ele = None
        except (TypeError, ValueError):
            ele = None
    return TrackPoint(parse_timestamp(time, timezone), lat, lon, ele, segment)


def _parse_records(data: dict[str, Any], timezone: ZoneInfo) -> tuple[list[TrackPoint], int]:
    points: list[TrackPoint] = []
    skipped = 0
    for item in data["locations"]:
        try:
            lat = float(item["latitudeE7"]) / 10_000_000
            lon = float(item["longitudeE7"]) / 10_000_000
            points.append(
                _point(
                    item.get("timestamp", item.get("timestampMs")),
                    {"lat": lat, "lon": lon},
                    timezone,
                    item.get("altitude"),
                )
            )
        except (KeyError, TypeError, ValueError, TimelineError):
            skipped += 1
    return points, skipped


def _parse_device(data: dict[str, Any], timezone: ZoneInfo) -> tuple[list[TrackPoint], int]:
    points: list[TrackPoint] = []
    skipped = 0
    segment_id = 0
    for item in data["semanticSegments"]:
        candidates: list[tuple[Any, Any, Any]] = []
        path = item.get("timelinePath") or []
        for path_point in path:
            path_time = path_point.get("time", path_point.get("timestamp"))
            if path_time is None and path_point.get("durationMinutesOffsetFromStartTime") is not None:
                try:
                    path_time = parse_timestamp(item.get("startTime"), timezone) + timedelta(
                        minutes=float(path_point["durationMinutesOffsetFromStartTime"])
                    )
                except (TypeError, ValueError, TimelineError):
                    path_time = None
            candidates.append(
                (
                    path_time,
                    path_point.get("point", path_point.get("latLng")),
                    path_point.get("altitudeMeters"),
                )
            )
        if not candidates:
            start = item.get("startTime")
            end = item.get("endTime")
            visit = item.get("visit") or item.get("placeVisit") or {}
            activity = item.get("activity") or item.get("activitySegment") or {}
            start_coord = (
                activity.get("start", {}).get("latLng")
                or activity.get("startLocation", {}).get("latLng")
                or visit.get("topCandidate", {}).get("placeLocation", {}).get("latLng")
                or visit.get("location", {}).get("latLng")
            )
            end_coord = (
                activity.get("end", {}).get("latLng")
                or activity.get("endLocation", {}).get("latLng")
                or start_coord
            )
            if start_coord:
                candidates.append((start, start_coord, None))
            if end_coord and end_coord != start_coord:
                candidates.append((end, end_coord, None))
        for time, coordinate, altitude in candidates:
            try:
                points.append(_point(time, coordinate, timezone, altitude, segment_id))
            except (TypeError, ValueError, TimelineError):
                skipped += 1
        segment_id += 1
    return points, skipped


def _semantic_location(container: dict[str, Any]) -> Any:
    if not isinstance(container, dict):
        return container
    latitude = container.get("latitudeE7", container.get("latE7"))
    longitude = container.get("longitudeE7", container.get("lngE7"))
    return (
        latitude is not None
        and longitude is not None
        and {
            "lat": float(latitude) / 10_000_000,
            "lon": float(longitude) / 10_000_000,
        }
        or container.get("latLng")
    )


def _parse_semantic(data: dict[str, Any], timezone: ZoneInfo) -> tuple[list[TrackPoint], int]:
    points: list[TrackPoint] = []
    skipped = 0
    for segment_id, item in enumerate(data["timelineObjects"]):
        candidates: list[tuple[Any, Any, Any]] = []
        if "activitySegment" in item:
            activity = item["activitySegment"]
            duration = activity.get("duration", {})
            path = (
                activity.get("simplifiedRawPath", {}).get("points")
                or activity.get("waypointPath", {}).get("waypoints")
                or []
            )
            for path_point in path:
                candidates.append(
                    (
                        path_point.get("timestamp", path_point.get("time")),
                        _semantic_location(path_point),
                        path_point.get("altitude"),
                    )
                )
            if not candidates:
                candidates.extend(
                    [
                        (duration.get("startTimestamp"), _semantic_location(activity.get("startLocation", {})), None),
                        (duration.get("endTimestamp"), _semantic_location(activity.get("endLocation", {})), None),
                    ]
                )
        elif "placeVisit" in item:
            visit = item["placeVisit"]
            duration = visit.get("duration", {})
            location = _semantic_location(visit.get("location", {}))
            candidates.append((duration.get("startTimestamp"), location, None))
            candidates.append((duration.get("endTimestamp"), location, None))
        for time, coordinate, altitude in candidates:
            try:
                points.append(_point(time, coordinate, timezone, altitude, segment_id))
            except (TypeError, ValueError, TimelineError):
                skipped += 1
    return points, skipped


def parse_data(data: Any, fallback_timezone: ZoneInfo) -> ParseResult:
    if not isinstance(data, dict):
        raise TimelineError("The JSON root must be an object.")
    if isinstance(data.get("semanticSegments"), list):
        points, skipped = _parse_device(data, fallback_timezone)
        name = "Device Timeline (semanticSegments)"
    elif isinstance(data.get("locations"), list):
        points, skipped = _parse_records(data, fallback_timezone)
        name = "Google Takeout Records.json"
    elif isinstance(data.get("timelineObjects"), list):
        points, skipped = _parse_semantic(data, fallback_timezone)
        name = "Google Takeout Semantic Location History"
    else:
        raise TimelineError("Unsupported Google Timeline JSON structure.")
    points.sort(key=lambda point: point.time)
    return ParseResult(points, (name,), skipped)


def discover_json_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    raise TimelineError(f"Input does not exist: {path}")


def load_path(path: Path, fallback_timezone: ZoneInfo) -> ParseResult:
    points: list[TrackPoint] = []
    formats: list[str] = []
    skipped = 0
    unsupported = 0
    files = discover_json_files(path)
    for file_path in files:
        try:
            with file_path.open("r", encoding="utf-8-sig") as file:
                result = parse_data(json.load(file), fallback_timezone)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TimelineError(f"Invalid JSON file: {file_path.name}") from exc
        except TimelineError:
            unsupported += 1
            continue
        points.extend(result.points)
        skipped += result.skipped
        formats.extend(result.format_names)
    if not formats:
        raise TimelineError("No supported Google Timeline JSON files were found.")
    points.sort(key=lambda point: point.time)
    return ParseResult(points, tuple(dict.fromkeys(formats)), skipped + unsupported)


def filter_points(points: Iterable[TrackPoint], start: datetime, end: datetime) -> list[TrackPoint]:
    if start.tzinfo is None or end.tzinfo is None:
        raise TimelineError("Filter timestamps must include a timezone.")
    if start > end:
        raise TimelineError("Start time must not be after end time.")
    start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)
    return [point for point in points if start_utc <= point.time <= end_utc]


def split_segments(points: Iterable[TrackPoint], gap: timedelta = timedelta(hours=2)) -> list[list[TrackPoint]]:
    segments: list[list[TrackPoint]] = []
    for point in sorted(points, key=lambda item: item.time):
        if (
            not segments
            or point.segment != segments[-1][-1].segment
            or point.time - segments[-1][-1].time > gap
        ):
            segments.append([point])
        else:
            segments[-1].append(point)
    return segments


def simplify_points(points: list[TrackPoint], maximum: int = 10_000) -> list[TrackPoint]:
    if len(points) <= maximum:
        return points
    stride = math.ceil(len(points) / maximum)
    simplified = points[::stride]
    if simplified[-1] != points[-1]:
        simplified.append(points[-1])
    return simplified
