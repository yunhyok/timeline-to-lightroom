from __future__ import annotations

from importlib.resources import files
from zoneinfo import available_timezones

from PySide6.QtCore import QLocale


def country_timezones() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    try:
        zone_tab = files("tzdata").joinpath("zoneinfo", "zone.tab").read_text(encoding="utf-8")
        for line in zone_tab.splitlines():
            if not line or line.startswith("#"):
                continue
            country_codes, _, timezone, *_ = line.split("\t")
            for country_code in country_codes.split(","):
                country = QLocale.territoryToString(QLocale.codeToTerritory(country_code))
                mapping.setdefault(country, []).append(timezone)
    except (FileNotFoundError, ModuleNotFoundError):
        mapping["All"] = sorted(available_timezones())
    return dict(sorted(mapping.items()))
