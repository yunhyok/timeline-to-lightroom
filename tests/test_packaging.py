from pathlib import Path


def test_pyinstaller_uses_package_launcher():
    spec = Path("TimelineToLightroom.spec").read_text(encoding="utf-8")
    launcher = Path("src/timeline_to_lightroom_launcher.py").read_text(encoding="utf-8")
    assert "src/timeline_to_lightroom_launcher.py" in spec
    assert "src/timeline_to_lightroom/app.py" not in spec
    assert "from timeline_to_lightroom.app import main" in launcher


def test_workflow_runs_built_executable_smoke_test():
    workflow = Path(".github/workflows/build-release.yml").read_text(encoding="utf-8")
    assert "TIMELINE_TO_LIGHTROOM_SMOKE_TEST" in workflow
    assert "TimelineToLightroom.exe" in workflow


def test_app_uses_pyside6_compatible_country_enum():
    app = Path("src/timeline_to_lightroom/app.py").read_text(encoding="utf-8")
    assert "QLocale.Country.SouthKorea" in app
    assert "QLocale.Territory.SouthKorea" not in app
