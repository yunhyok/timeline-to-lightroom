from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from timeline_to_lightroom.core import TimelineError, filter_points, parse_data, simplify_points


SEOUL = ZoneInfo("Asia/Seoul")


def test_parse_records_and_filter_boundaries():
    result = parse_data(
        {
            "locations": [
                {"timestamp": "2025-01-01T00:00:00Z", "latitudeE7": 375000000, "longitudeE7": 1270000000},
                {"timestamp": "2025-01-01T01:00:00Z", "latitudeE7": 376000000, "longitudeE7": 1271000000},
                {"timestamp": "bad", "latitudeE7": 0, "longitudeE7": 0},
            ]
        },
        SEOUL,
    )
    assert len(result.points) == 2
    assert result.skipped == 1
    selected = filter_points(
        result.points,
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
    )
    assert len(selected) == 1
    assert selected[0].latitude == 37.5


def test_parse_device_timeline_path_and_offset():
    result = parse_data(
        {
            "semanticSegments": [
                {
                    "startTime": "2025-01-01T09:00:00+09:00",
                    "endTime": "2025-01-01T10:00:00+09:00",
                    "timelinePath": [
                        {"time": "2025-01-01T09:00:00+09:00", "point": "37.5°, 127.0°"},
                        {"time": "2025-01-01T10:00:00+09:00", "point": "37.6°, 127.1°"},
                    ],
                }
            ]
        },
        SEOUL,
    )
    assert [point.time.hour for point in result.points] == [0, 1]


def test_parse_device_duration_offset():
    result = parse_data(
        {
            "semanticSegments": [
                {
                    "startTime": "2025-01-01T00:00:00Z",
                    "timelinePath": [
                        {"durationMinutesOffsetFromStartTime": "15", "point": "10.0, 20.0"}
                    ],
                }
            ]
        },
        SEOUL,
    )
    assert result.points[0].time.minute == 15


def test_parse_takeout_semantic():
    result = parse_data(
        {
            "timelineObjects": [
                {
                    "activitySegment": {
                        "duration": {
                            "startTimestamp": "2025-01-01T00:00:00Z",
                            "endTimestamp": "2025-01-01T01:00:00Z",
                        },
                        "startLocation": {"latitudeE7": 100000000, "longitudeE7": 200000000},
                        "endLocation": {"latitudeE7": 110000000, "longitudeE7": 210000000},
                    }
                }
            ]
        },
        SEOUL,
    )
    assert len(result.points) == 2
    assert result.points[-1].longitude == 21


def test_parse_takeout_semantic_lng_e7_path():
    result = parse_data(
        {
            "timelineObjects": [
                {
                    "activitySegment": {
                        "simplifiedRawPath": {
                            "points": [
                                {
                                    "timestamp": "2025-01-01T00:00:00Z",
                                    "latE7": 100000000,
                                    "lngE7": 200000000,
                                }
                            ]
                        }
                    }
                }
            ]
        },
        SEOUL,
    )
    assert result.points[0].longitude == 20


def test_naive_timestamp_uses_selected_timezone():
    result = parse_data(
        {"locations": [{"timestamp": "2025-01-01T09:00:00", "latitudeE7": 0, "longitudeE7": 0}]},
        SEOUL,
    )
    assert result.points[0].time == datetime(2025, 1, 1, 0, 0, tzinfo=UTC)


def test_unsupported_structure():
    with pytest.raises(TimelineError):
        parse_data({"anything": []}, SEOUL)


def test_simplification_keeps_endpoints():
    result = parse_data(
        {
            "locations": [
                {"timestamp": f"2025-01-01T00:00:{second:02d}Z", "latitudeE7": second, "longitudeE7": second}
                for second in range(20)
            ]
        },
        SEOUL,
    )
    simplified = simplify_points(result.points, 5)
    assert simplified[0] == result.points[0]
    assert simplified[-1] == result.points[-1]
    assert len(simplified) <= 6
