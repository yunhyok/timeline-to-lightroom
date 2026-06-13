from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TrackPoint:
    time: datetime
    latitude: float
    longitude: float
    altitude: float | None = None
    segment: int = 0


@dataclass(frozen=True, slots=True)
class ParseResult:
    points: list[TrackPoint]
    format_names: tuple[str, ...]
    skipped: int = 0

