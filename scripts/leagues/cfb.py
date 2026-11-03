"""College football (FBS): schedule from ESPN (groups=80), win probability from sportsdataverse's
ESPN-processed play-by-play parquet. Game ids match ESPN's."""
from __future__ import annotations

from datetime import date

import pandas as pd

from common import RAW, download, log
from leagues.base import League

PBP_URL = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/play_by_play_{season}.parquet"


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

    def __init__(self):
        super().__init__()
        self._pbp: pd.DataFrame | None = None

    def team_params(self):
        return {"groups": 80}

    def prepare_wp(self, todo):
        path = download(PBP_URL.format(season=self.season), RAW / f"cfb_pbp_{self.season}.parquet", max_age_s=20 * 60)
        cols = ["game_id", "period", "start.adj_TimeSecsRem", "home_wp_before", "game_play_number"]
        df = pd.read_parquet(path, columns=cols)
        df["game_id"] = df["game_id"].astype(str)
        wanted = {g["id"] for g in todo}
        df = df[df["game_id"].isin(wanted)].sort_values(["game_id", "game_play_number"])
        self._pbp = df
        log("cfb", f"parquet: {df['game_id'].nunique()} of {len(wanted)} wanted games present")

    def wp_series(self, g):
        p = self._pbp[self._pbp["game_id"] == g["id"]]
        p = p[p["home_wp_before"].notna()]
        if len(p) < 60:
            return None
        wp = p["home_wp_before"].to_list()
        rem = p["start.adj_TimeSecsRem"].fillna(0).to_list()
        ot = (p["period"].fillna(4) >= 5).to_list()
        home_won = None
        if g.get("result"):
            home_won = g["result"]["home"] > g["result"]["away"]
        g["source"] = dict(wp="sportsdataverse-espn")
        return self.finalize_series(wp, rem, ot, home_won)

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
