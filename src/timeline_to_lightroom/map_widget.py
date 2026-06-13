from __future__ import annotations

import json
from importlib.resources import files

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from .core import simplify_points
from .models import TrackPoint


class MapWidget(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending: list[TrackPoint] = []
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        map_path = files("timeline_to_lightroom").joinpath("assets", "map.html")
        self.loadFinished.connect(self._loaded)
        self.setUrl(QUrl.fromLocalFile(str(map_path)))

    def set_points(self, points: list[TrackPoint]) -> None:
        self._pending = simplify_points(points)
        if self.url().isValid():
            self._send()

    def fit_track(self) -> None:
        self.page().runJavaScript("fitTrack();")

    def _loaded(self, success: bool) -> None:
        if success:
            self._send()

    def _send(self) -> None:
        coordinates = [[point.latitude, point.longitude] for point in self._pending]
        self.page().runJavaScript(f"setTrack({json.dumps(coordinates)});")

