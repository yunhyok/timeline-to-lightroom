from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QDateTime, QLocale, QObject, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .core import TimelineError, filter_points, load_path
from .exporters import write_gpx, write_kml
from .map_widget import MapWidget
from .models import ParseResult, TrackPoint
from .timezones import country_timezones


TEXT = {
    "ko": {
        "title": "Timeline to Lightroom",
        "settings": "변환 설정",
        "map": "지도 미리보기",
        "input": "입력 JSON 파일/폴더",
        "browse_file": "파일 선택",
        "browse_folder": "폴더 선택",
        "country": "국가",
        "timezone": "시간대",
        "start": "시작 일시",
        "end": "종료 일시",
        "output": "출력 폴더",
        "browse": "선택",
        "kml": "KML도 생성",
        "convert": "GPX 변환",
        "fit": "전체 경로 맞춤",
        "ready": "입력 JSON 파일 또는 폴더를 선택하십시오.",
        "loaded": "{formats} | 전체 {total:,}개, 선택 {selected:,}개, 제외 {skipped:,}개",
        "empty": "선택 기간에 위치 데이터가 없습니다.",
        "done": "출력 완료:\n{files}",
        "error": "오류",
        "overwrite": "기존 파일을 덮어쓰시겠습니까?\n{files}",
    },
    "en": {
        "title": "Timeline to Lightroom",
        "settings": "Conversion",
        "map": "Map Preview",
        "input": "Input JSON file/folder",
        "browse_file": "Choose File",
        "browse_folder": "Choose Folder",
        "country": "Country",
        "timezone": "Time zone",
        "start": "Start",
        "end": "End",
        "output": "Output folder",
        "browse": "Choose",
        "kml": "Also create KML",
        "convert": "Convert to GPX",
        "fit": "Fit entire track",
        "ready": "Choose an input JSON file or folder.",
        "loaded": "{formats} | total {total:,}, selected {selected:,}, skipped {skipped:,}",
        "empty": "No location data exists in the selected period.",
        "done": "Export complete:\n{files}",
        "error": "Error",
        "overwrite": "Overwrite existing files?\n{files}",
    },
}


class LoadWorker(QObject):
    completed = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path: Path, timezone: ZoneInfo):
        super().__init__()
        self.path = path
        self.timezone = timezone

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self.path, load_path(self.path, self.timezone))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.language = "ko"
        self.result: ParseResult | None = None
        self.selected: list[TrackPoint] = []
        self._load_thread: QThread | None = None
        self._load_worker: LoadWorker | None = None
        self.countries = country_timezones()
        self._build_ui()
        self._populate_countries()
        self._retranslate()
        self.resize(1080, 720)

    def t(self, key: str) -> str:
        return TEXT[self.language][key]

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        settings = QWidget()
        outer = QVBoxLayout(settings)
        top = QHBoxLayout()
        top.addStretch()
        self.language_combo = QComboBox()
        self.language_combo.addItem("한국어", "ko")
        self.language_combo.addItem("English", "en")
        self.language_combo.currentIndexChanged.connect(self._change_language)
        top.addWidget(self.language_combo)
        outer.addLayout(top)

        form = QFormLayout()
        self.input_edit = QLineEdit()
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_edit)
        self.file_button = QPushButton()
        self.folder_button = QPushButton()
        input_row.addWidget(self.file_button)
        input_row.addWidget(self.folder_button)
        self.input_label = QLabel()
        form.addRow(self.input_label, input_row)

        self.country_combo = QComboBox()
        self.country_combo.setEditable(True)
        self.country_combo.currentIndexChanged.connect(self._country_changed)
        self.timezone_combo = QComboBox()
        self.timezone_combo.setEditable(True)
        self.timezone_combo.currentTextChanged.connect(self._timezone_changed)
        self.country_label = QLabel()
        self.timezone_label = QLabel()
        form.addRow(self.country_label, self.country_combo)
        form.addRow(self.timezone_label, self.timezone_combo)

        self.start_edit = QDateTimeEdit(calendarPopup=True)
        self.end_edit = QDateTimeEdit(calendarPopup=True)
        for edit in (self.start_edit, self.end_edit):
            edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            edit.dateTimeChanged.connect(self._schedule_filter)
        self.start_label = QLabel()
        self.end_label = QLabel()
        form.addRow(self.start_label, self.start_edit)
        form.addRow(self.end_label, self.end_edit)

        self.output_edit = QLineEdit(str(Path.home() / "Documents"))
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        self.output_button = QPushButton()
        output_row.addWidget(self.output_button)
        self.output_label = QLabel()
        form.addRow(self.output_label, output_row)

        self.kml_check = QCheckBox()
        form.addRow("", self.kml_check)
        outer.addLayout(form)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        outer.addWidget(self.progress)
        self.convert_button = QPushButton()
        self.convert_button.setEnabled(False)
        outer.addWidget(self.convert_button)
        outer.addStretch()

        map_page = QWidget()
        map_layout = QVBoxLayout(map_page)
        self.map_widget = MapWidget()
        map_layout.addWidget(self.map_widget)
        self.fit_button = QPushButton()
        map_layout.addWidget(self.fit_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(settings, "")
        self.tabs.addTab(map_page, "")

        self.file_button.clicked.connect(self._choose_file)
        self.folder_button.clicked.connect(self._choose_folder)
        self.output_button.clicked.connect(self._choose_output)
        self.convert_button.clicked.connect(self._convert)
        self.fit_button.clicked.connect(self.map_widget.fit_track)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_filter)

    def _populate_countries(self) -> None:
        self.country_combo.addItems(self.countries.keys())
        for index in range(self.country_combo.count()):
            if self.country_combo.itemText(index) in ("South Korea", "대한민국"):
                self.country_combo.setCurrentIndex(index)
                break
        self._country_changed()
        target = self.timezone_combo.findText("Asia/Seoul")
        if target >= 0:
            self.timezone_combo.setCurrentIndex(target)

    def _country_changed(self) -> None:
        country = self.country_combo.currentText()
        current = self.timezone_combo.currentText()
        self.timezone_combo.blockSignals(True)
        self.timezone_combo.clear()
        self.timezone_combo.addItems(self.countries.get(country, []))
        index = self.timezone_combo.findText(current)
        if index >= 0:
            self.timezone_combo.setCurrentIndex(index)
        self.timezone_combo.blockSignals(False)

    def _change_language(self) -> None:
        self.language = self.language_combo.currentData()
        self._retranslate()

    def _retranslate(self) -> None:
        self.setWindowTitle(self.t("title"))
        self.tabs.setTabText(0, self.t("settings"))
        self.tabs.setTabText(1, self.t("map"))
        self.input_label.setText(self.t("input"))
        self.file_button.setText(self.t("browse_file"))
        self.folder_button.setText(self.t("browse_folder"))
        self.country_label.setText(self.t("country"))
        self.timezone_label.setText(self.t("timezone"))
        self.start_label.setText(self.t("start"))
        self.end_label.setText(self.t("end"))
        self.output_label.setText(self.t("output"))
        self.output_button.setText(self.t("browse"))
        self.kml_check.setText(self.t("kml"))
        self.convert_button.setText(self.t("convert"))
        self.fit_button.setText(self.t("fit"))
        if not self.result:
            self.status_label.setText(self.t("ready"))
        else:
            self._update_status()

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.t("input"), "", "JSON (*.json)")
        if path:
            self._load(Path(path))

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.t("input"))
        if path:
            self._load(Path(path))

    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.t("output"), self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def _timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone_combo.currentText())
        except Exception:
            return ZoneInfo("Asia/Seoul")

    def _timezone_changed(self) -> None:
        if self.result:
            self._set_range()
            self._apply_filter()

    def _load(self, path: Path) -> None:
        if self._load_thread and self._load_thread.isRunning():
            return
        self.progress.setRange(0, 0)
        self.file_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self._load_thread = QThread(self)
        self._load_worker = LoadWorker(path, self._timezone())
        self._load_worker.moveToThread(self._load_thread)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.completed.connect(self._load_completed)
        self._load_worker.failed.connect(self._load_failed)
        self._load_worker.completed.connect(self._load_thread.quit)
        self._load_worker.failed.connect(self._load_thread.quit)
        self._load_thread.finished.connect(self._load_worker.deleteLater)
        self._load_thread.finished.connect(self._load_cleanup)
        self._load_thread.start()

    @Slot(object, object)
    def _load_completed(self, path: Path, result: ParseResult) -> None:
        self.result = result
        self.input_edit.setText(str(path))
        self._set_range()
        self._apply_filter()

    @Slot(str)
    def _load_failed(self, message: str) -> None:
        QMessageBox.critical(self, self.t("error"), message)

    @Slot()
    def _load_cleanup(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if self.result else 0)
        self.file_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        if self._load_thread:
            self._load_thread.deleteLater()
        self._load_worker = None
        self._load_thread = None

    def closeEvent(self, event) -> None:
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait()
        super().closeEvent(event)

    def _set_range(self) -> None:
        if not self.result or not self.result.points:
            return
        timezone = self._timezone()
        start = self.result.points[0].time.astimezone(timezone).replace(tzinfo=None)
        end = self.result.points[-1].time.astimezone(timezone).replace(tzinfo=None)
        self.start_edit.blockSignals(True)
        self.end_edit.blockSignals(True)
        self.start_edit.setDateTime(QDateTime(start))
        self.end_edit.setDateTime(QDateTime(end))
        self.start_edit.blockSignals(False)
        self.end_edit.blockSignals(False)

    def _schedule_filter(self) -> None:
        self._filter_timer.start()

    def _apply_filter(self) -> None:
        if not self.result:
            return
        timezone = self._timezone()
        start = self.start_edit.dateTime().toPython().replace(tzinfo=timezone)
        end = self.end_edit.dateTime().toPython().replace(tzinfo=timezone)
        try:
            self.selected = filter_points(self.result.points, start, end)
        except TimelineError as exc:
            self.status_label.setText(str(exc))
            self.selected = []
        self.map_widget.set_points(self.selected)
        self.convert_button.setEnabled(bool(self.selected))
        self._update_status()

    def _update_status(self) -> None:
        if not self.result:
            return
        self.status_label.setText(
            self.t("loaded").format(
                formats=", ".join(self.result.format_names),
                total=len(self.result.points),
                selected=len(self.selected),
                skipped=self.result.skipped,
            )
        )

    def _convert(self) -> None:
        if not self.selected:
            QMessageBox.information(self, self.t("title"), self.t("empty"))
            return
        output = Path(self.output_edit.text()).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        timezone = self._timezone()
        start = self.selected[0].time.astimezone(timezone).strftime("%Y%m%d_%H%M")
        end = self.selected[-1].time.astimezone(timezone).strftime("%Y%m%d_%H%M")
        base = output / f"timeline_{start}_{end}"
        paths = [base.with_suffix(".gpx")]
        if self.kml_check.isChecked():
            paths.append(base.with_suffix(".kml"))
        existing = [path for path in paths if path.exists()]
        if existing:
            answer = QMessageBox.question(
                self,
                self.t("title"),
                self.t("overwrite").format(files="\n".join(map(str, existing))),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            write_gpx(paths[0], self.selected)
            if self.kml_check.isChecked():
                write_kml(paths[1], self.selected)
            QMessageBox.information(
                self, self.t("title"), self.t("done").format(files="\n".join(map(str, paths)))
            )
        except OSError as exc:
            QMessageBox.critical(self, self.t("error"), str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Timeline to Lightroom")
    app.setOrganizationName("yunhyok")
    QLocale.setDefault(QLocale(QLocale.Language.Korean, QLocale.Territory.SouthKorea))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
