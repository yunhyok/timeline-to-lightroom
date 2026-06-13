from __future__ import annotations

from datetime import UTC
from pathlib import Path
from xml.etree import ElementTree as ET

from .core import split_segments
from .models import TrackPoint

GPX_NS = "http://www.topografix.com/GPX/1/1"
KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS = "http://www.google.com/kml/ext/2.2"


def _time(point: TrackPoint) -> str:
    return point.time.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_gpx(path: Path, points: list[TrackPoint]) -> None:
    ET.register_namespace("", GPX_NS)
    root = ET.Element(
        f"{{{GPX_NS}}}gpx",
        {"version": "1.1", "creator": "Timeline to Lightroom"},
    )
    track = ET.SubElement(root, f"{{{GPX_NS}}}trk")
    ET.SubElement(track, f"{{{GPX_NS}}}name").text = path.stem
    for segment in split_segments(points):
        trkseg = ET.SubElement(track, f"{{{GPX_NS}}}trkseg")
        for point in segment:
            trkpt = ET.SubElement(
                trkseg,
                f"{{{GPX_NS}}}trkpt",
                {"lat": f"{point.latitude:.7f}", "lon": f"{point.longitude:.7f}"},
            )
            if point.altitude is not None:
                ET.SubElement(trkpt, f"{{{GPX_NS}}}ele").text = f"{point.altitude:.2f}"
            ET.SubElement(trkpt, f"{{{GPX_NS}}}time").text = _time(point)
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_kml(path: Path, points: list[TrackPoint]) -> None:
    ET.register_namespace("", KML_NS)
    ET.register_namespace("gx", GX_NS)
    root = ET.Element(f"{{{KML_NS}}}kml")
    document = ET.SubElement(root, f"{{{KML_NS}}}Document")
    ET.SubElement(document, f"{{{KML_NS}}}name").text = path.stem
    for index, segment in enumerate(split_segments(points), start=1):
        placemark = ET.SubElement(document, f"{{{KML_NS}}}Placemark")
        ET.SubElement(placemark, f"{{{KML_NS}}}name").text = f"Track {index}"
        track = ET.SubElement(placemark, f"{{{GX_NS}}}Track")
        for point in segment:
            ET.SubElement(track, f"{{{KML_NS}}}when").text = _time(point)
        for point in segment:
            altitude = point.altitude if point.altitude is not None else 0
            ET.SubElement(track, f"{{{GX_NS}}}coord").text = (
                f"{point.longitude:.7f} {point.latitude:.7f} {altitude:.2f}"
            )
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

