"""NBA: schedule and per-play win probability both from ESPN's game summary endpoint."""
from __future__ import annotations

from datetime import date

from leagues.base import League

PERIOD_SECONDS = 720.0


class NBA(League):
    slug = "nba"
    name = "NBA"
    short = "NBA"
    cadence = "daily"
    reg_seconds = 4 * PERIOD_SECONDS
    espn_path = "basketball/nba"
    season = "2026-27"
    season_start = date(2026, 10, 20)
    youtube_channel = "UCWJ2lWNubArHWmf3FIHbfcQ"

    def wp_series(self, g):
        return self.espn_wp_series(g, period_seconds=PERIOD_SECONDS, regulation_periods=4)
