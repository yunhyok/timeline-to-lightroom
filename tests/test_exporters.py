from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET

from timeline_to_lightroom.exporters import GPX_NS, GX_NS, KML_NS, write_gpx, write_kml
from timeline_to_lightroom.models import TrackPoint


def sample_points():
    return [
        TrackPoint(datetime(2025, 1, 1, tzinfo=UTC), 37.5, 127.0, 10, 0),
        TrackPoint(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=1), 37.6, 127.1, None, 0),
    ]


def test_write_gpx(tmp_path):
    path = tmp_path / "track.gpx"
    write_gpx(path, sample_points())
    root = ET.parse(path).getroot()
    points = root.findall(f".//{{{GPX_NS}}}trkpt")
    assert len(points) == 2
    assert points[0].find(f"{{{GPX_NS}}}time").text.endswith("Z")


def test_write_kml(tmp_path):
    path = tmp_path / "track.kml"
    write_kml(path, sample_points())
    root = ET.parse(path).getroot()
    assert len(root.findall(f".//{{{GX_NS}}}coord")) == 2
    assert len(root.findall(f".//{{{KML_NS}}}when")) == 2
