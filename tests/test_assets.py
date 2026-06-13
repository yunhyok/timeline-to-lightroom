from importlib.resources import files

from timeline_to_lightroom.timezones import country_timezones


def test_map_assets_include_interactions_and_fallback():
    html = files("timeline_to_lightroom").joinpath("assets", "map.html").read_text(encoding="utf-8")
    assert 'event.button === 1' in html
    assert "fitBounds" in html
    assert "showOffline" in html
    assert "while (lon - previous > 180)" in html


def test_country_timezone_mapping_contains_seoul():
    mapping = country_timezones()
    assert "Asia/Seoul" in mapping["South Korea"]
