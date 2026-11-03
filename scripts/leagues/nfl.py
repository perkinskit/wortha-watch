"""NFL: schedule from ESPN, win probability from nflverse play-by-play (spread-adjusted model)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from common import RAW, download, log
from leagues.base import League

PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
# nflverse abbreviation -> ESPN abbreviation
ABBR = {"LA": "LAR", "WAS": "WSH"}

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

    def __init__(self):
        super().__init__()
        self._pbp: pd.DataFrame | None = None
        self._by_key: dict[tuple[str, str], str] = {}

    def prepare_wp(self, todo):
        path = download(PBP_URL.format(season=self.season), RAW / f"nfl_pbp_{self.season}.csv.gz", max_age_s=20 * 60)
        cols = ["game_id", "game_date", "home_team", "away_team", "qtr", "play_id", "game_seconds_remaining",
                "desc", "vegas_home_wp", "home_wp"]
        df = pd.read_csv(path, usecols=cols, low_memory=False).sort_values(["game_id", "play_id"])
        ended = set(df.loc[df["desc"] == "END GAME", "game_id"])
        df = df[df["game_id"].isin(ended)]
        self._pbp = df
        # nflverse game_date is the ET game date; key on (date, espn home abbr)
        first = df.groupby("game_id").first()
        self._by_key = {(r["game_date"], ABBR.get(r["home_team"], r["home_team"])): gid for gid, r in first.iterrows()}
        log("nfl", f"nflverse: {len(ended)} completed games in file")

    def wp_series(self, g):
        key = (g["date_et"], g["home"]["abbr"])
        gid = self._by_key.get(key)
        if not gid:
            return None
        p = self._pbp[self._pbp["game_id"] == gid]
        wpcol = "vegas_home_wp" if p["vegas_home_wp"].notna().mean() > 0.9 else "home_wp"
        p = p[p[wpcol].notna()]
        wp = p[wpcol].to_list()
        rem = p["game_seconds_remaining"].fillna(0).to_list()
        ot = (p["qtr"].fillna(4) >= 5).to_list()
        g["source"] = dict(wp="nflverse", game_id=gid)
        return wp, rem, ot

    def extra_stakes(self, g):
        h, a = g["home"]["abbr"], g["away"]["abbr"]
        pair = frozenset((h, a))
        return dict(
            division=DIV_OF.get(h) is not None and DIV_OF.get(h) == DIV_OF.get(a),
            rivalry=10 if pair in BIG_RIVALRIES else 5 if pair in RIVALRIES else 0,
        )
