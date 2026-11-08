"""NFL: schedule and per-play win probability from ESPN (available minutes after the final whistle)."""
from __future__ import annotations

from datetime import date

from leagues.base import League

RIVALRIES = {frozenset(p) for p in [
    ("CLE", "PIT"), ("PIT", "BAL"), ("BAL", "CIN"), ("CIN", "PIT"), ("CIN", "CLE"),
    ("GB", "CHI"), ("GB", "MIN"), ("GB", "DET"), ("DET", "MIN"), ("CHI", "MIN"), ("CHI", "DET"),
    ("DAL", "PHI"), ("DAL", "WSH"), ("DAL", "NYG"), ("PHI", "NYG"), ("PHI", "WSH"), ("NYG", "WSH"),
    ("KC", "LV"), ("DEN", "LV"), ("KC", "DEN"), ("LAC", "LV"), ("KC", "LAC"), ("DEN", "LAC"),
    ("SF", "SEA"), ("SF", "LAR"), ("SEA", "LAR"), ("ARI", "SF"), ("ARI", "SEA"), ("ARI", "LAR"),
    ("NE", "NYJ"), ("BUF", "MIA"), ("NE", "MIA"), ("NE", "BUF"), ("NYJ", "MIA"), ("NYJ", "BUF"),
    ("NO", "ATL"), ("TB", "NO"), ("ATL", "TB"), ("CAR", "ATL"), ("CAR", "NO"), ("CAR", "TB"),
    ("IND", "JAX"), ("IND", "TEN"), ("IND", "HOU"), ("JAX", "TEN"), ("HOU", "TEN"), ("HOU", "JAX"),
    ("LAC", "LAR"), ("NYG", "NYJ"),
]}
BIG_RIVALRIES = {frozenset(p) for p in [
    ("CLE", "PIT"), ("PIT", "BAL"), ("GB", "CHI"), ("GB", "MIN"), ("DAL", "PHI"), ("DAL", "WSH"),
    ("KC", "LV"), ("DEN", "LV"), ("KC", "DEN"), ("SF", "SEA"), ("NE", "NYJ"), ("BUF", "MIA"),
    ("NO", "ATL"), ("BAL", "CIN"), ("DET", "GB"), ("DET", "MIN"), ("LAC", "LAR"), ("PHI", "WSH"),
]}
DIVISIONS = {
    "AFC East": ["BUF", "MIA", "NE", "NYJ"], "AFC North": ["BAL", "CIN", "CLE", "PIT"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"], "AFC West": ["DEN", "KC", "LV", "LAC"],
    "NFC East": ["DAL", "NYG", "PHI", "WSH"], "NFC North": ["CHI", "DET", "GB", "MIN"],
    "NFC South": ["ATL", "CAR", "NO", "TB"], "NFC West": ["ARI", "LAR", "SF", "SEA"],
}
DIV_OF = {t: d for d, ts in DIVISIONS.items() for t in ts}


class NFL(League):
    slug = "nfl"
    name = "NFL"
    short = "NFL"
    cadence = "weekly"
    reg_seconds = 3600.0
    espn_path = "football/nfl"
    season = "2026"
    season_start = date(2026, 9, 1)
    youtube_channel = "UCDVYQ4Zhbm3S2dlz7P1GBDg"
    week_count = 18

    def wp_series(self, g):
        return self.espn_wp_series(g, period_seconds=900.0, regulation_periods=4)

    def extra_stakes(self, g):
        h, a = g["home"]["abbr"], g["away"]["abbr"]
        pair = frozenset((h, a))
        return dict(
            division=DIV_OF.get(h) is not None and DIV_OF.get(h) == DIV_OF.get(a),
            rivalry=10 if pair in BIG_RIVALRIES else 5 if pair in RIVALRIES else 0,
        )
