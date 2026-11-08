"""College football (FBS): schedule (groups=80) and per-play win probability from ESPN."""
from __future__ import annotations

from datetime import date

from leagues.base import League


class CFB(League):
    slug = "cfb"
    name = "College Football"
    short = "CFB"
    cadence = "weekly"
    reg_seconds = 3600.0
    espn_path = "football/college-football"
    season = "2026"
    season_start = date(2026, 8, 23)
    youtube_channel = None          # highlights column intentionally empty for now
    espn_scoreboard_params = {"groups": 80}
    week_count = 16

    def wp_series(self, g):
        return self.espn_wp_series(g, period_seconds=900.0, regulation_periods=4)

    def extra_stakes(self, g):
        e = g.get("espn", {})
        hr, ar = e.get("home_rank") or 99, e.get("away_rank") or 99
        bonus = 0.0
        for r in (hr, ar):
            if r <= 5:
                bonus += 14
            elif r <= 10:
                bonus += 10
            elif r <= 25:
                bonus += 6
        return dict(conference=bool(e.get("conference")), division=bool(e.get("conference")),
                    ranked=[r for r in (hr, ar) if r <= 25], ranked_bonus=bonus)
