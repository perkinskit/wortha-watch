"""NBA: schedule and per-play win probability both from ESPN's game summary endpoint."""
from __future__ import annotations

from datetime import date

from common import clock_to_seconds, espn
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
        s = espn(f"{self.espn_path}/summary", event=g["id"])
        wps = s.get("winprobability") or []
        if len(wps) < 20:
            return None
        plays = {p["id"]: p for p in s.get("plays", [])}
        wp, rem, ot = [], [], []
        for e in wps:
            p = plays.get(e.get("playId"))
            if not p:
                continue
            period = int((p.get("period") or {}).get("number") or 1)
            clock = clock_to_seconds((p.get("clock") or {}).get("displayValue", "0:00"))
            if period <= 4:
                rem.append((4 - period) * PERIOD_SECONDS + clock)
                ot.append(False)
            else:
                rem.append(0.0)
                ot.append(True)
            wp.append(float(e.get("homeWinPercentage", 0.5)))
        if len(wp) < 20:
            return None
        home_won = g["result"]["home"] > g["result"]["away"] if g.get("result") else None
        g["source"] = dict(wp="espn")
        return self.finalize_series(wp, rem, ot, home_won)
