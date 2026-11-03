"""League base: ESPN schedule/teams handling, the per-season game store, stakes from records.

Each league subclass supplies:
  slug, name, cadence ('weekly'|'daily'), reg_seconds, espn_path, season label, season_start (date),
  youtube_channel (or None), and a `wp_series(game) -> (wp, rem, is_ot) | None` for completed games,
  plus `extra_stakes(game) -> dict(flags/bonus)`.

Store: data/<slug>/<season>/games.json  {game_id: record}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np

from common import DATA, espn, et_date, et_time_label, day_label, hex_color, load_json, log, parse_espn_date, save_json, utc_now, ET
from scoring import raw_metrics, rec_str, stakes_score


@dataclass
class Team:
    id: str
    abbr: str
    name: str      # "Kansas City Chiefs"
    nick: str      # "Chiefs"
    short: str     # "Kansas City"
    color: str
    alt: str

    def as_dict(self):
        return self.__dict__.copy()


class League:
    slug = ""
    name = ""
    short = ""
    cadence = "weekly"        # or 'daily'
    reg_seconds = 3600.0
    espn_path = ""            # e.g. 'football/nfl'
    season = ""               # label used in paths, e.g. '2026' or '2026-27'
    season_start = date(2026, 9, 1)
    youtube_channel: str | None = None
    espn_scoreboard_params: dict = {}
    week_count = 18

    def __init__(self):
        self.dir = DATA / self.slug / self.season
        self.games_path = self.dir / "games.json"
        self.teams_path = DATA / self.slug / "teams.json"
        self.games: dict[str, dict] = load_json(self.games_path, {})
        self.teams: dict[str, dict] = load_json(self.teams_path, {})

    # ---------- teams ----------
    def load_teams(self, force: bool = False) -> None:
        if self.teams and not force:
            return
        j = espn(f"{self.espn_path}/teams", limit=1000, **self.team_params())
        out = {}
        for entry in j["sports"][0]["leagues"][0]["teams"]:
            t = entry["team"]
            out[t["id"]] = Team(
                id=t["id"], abbr=t.get("abbreviation", "???"), name=t.get("displayName", ""),
                nick=t.get("name") or t.get("shortDisplayName", ""), short=t.get("location", ""),
                color=hex_color(t.get("color"), "#444c5c"), alt=hex_color(t.get("alternateColor"), "#c9d1e0"),
            ).as_dict()
        self.teams = out
        save_json(self.teams_path, out)

    def team_params(self) -> dict:
        return {}

    def team_by_abbr(self, abbr: str) -> dict | None:
        for t in self.teams.values():
            if t["abbr"] == abbr:
                return t
        return None

    # ---------- schedule via ESPN scoreboard ----------
    def scoreboard_pages(self) -> list[dict]:
        """Which scoreboard requests to make this run. Weekly leagues: weeks not yet complete + current.
        Daily leagues: dates from the last incomplete date through today (ET)."""
        if self.cadence == "weekly":
            cur = self.current_week()
            have = {g["period_sort"] for g in self.games.values()}
            weeks = {w for w in range(1, cur + 1) if w not in have} | {cur}
            weeks |= {g["period_sort"] for g in self.games.values() if g["status"] != "final"}
            return [dict(week=w, seasontype=2, **self.espn_scoreboard_params) for w in sorted(weeks)]
        today = datetime.now(ET).date()
        if not self.games:
            start = self.season_start
        else:
            pending = [date.fromisoformat(g["date_et"]) for g in self.games.values() if g["status"] != "final"]
            start = min(pending + [today - timedelta(days=1)])
        out = []
        d = start
        while d <= today:
            out.append(dict(dates=d.strftime("%Y%m%d"), **self.espn_scoreboard_params))
            d += timedelta(days=1)
        return out

    def current_week(self) -> int:
        j = espn(f"{self.espn_path}/scoreboard", **self.espn_scoreboard_params)
        wk = (j.get("week") or {}).get("number")
        if wk:
            return int(wk)
        return max([g["period_sort"] for g in self.games.values()] + [1])

    def sync_schedule(self) -> None:
        """Create/refresh game records (teams, status, period, records, ranks) from ESPN scoreboards."""
        self.load_teams()
        for params in self.scoreboard_pages():
            try:
                j = espn(f"{self.espn_path}/scoreboard", limit=300, **params)
            except Exception as e:  # noqa: BLE001
                log(self.slug, "scoreboard failed", params, e)
                continue
            for ev in j.get("events", []):
                self.ingest_event(ev, j)
        save_json(self.games_path, self.games)

    def ingest_event(self, ev: dict, page: dict) -> None:
        comp = ev["competitions"][0]
        status = comp["status"]["type"]
        state = "final" if status.get("completed") else ("live" if status.get("state") == "in" else "pending")
        start = parse_espn_date(ev["date"])
        home = away = None
        for c in comp["competitors"]:
            t = self.teams.get(c["team"]["id"]) or Team(
                id=c["team"]["id"], abbr=c["team"].get("abbreviation", "???"), name=c["team"].get("displayName", ""),
                nick=c["team"].get("name", ""), short=c["team"].get("location", ""),
                color=hex_color(c["team"].get("color"), "#444c5c"), alt=hex_color(c["team"].get("alternateColor"), "#c9d1e0")).as_dict()
            side = dict(team=t, score=int(c.get("score") or 0) if state == "final" else None,
                        rank=(c.get("curatedRank") or {}).get("current"),
                        record=(c.get("records") or [{}])[0].get("summary"))
            if c["homeAway"] == "home":
                home = side
            else:
                away = side
        if not home or not away:
            return
        gid = ev["id"]
        rec = self.games.get(gid, {})
        period_sort, period, period_label = self.period_for(ev, page, start)
        rec.update(
            id=gid, season=self.season, status=state, start_utc=start.isoformat(), date_et=et_date(start),
            period=period, period_sort=period_sort, period_label=period_label,
            home=home["team"], away=away["team"],
            labels=dict(day=day_label(start), time=et_time_label(start)),
            espn=dict(home_rank=home["rank"], away_rank=away["rank"], conference=bool(comp.get("conferenceCompetition")),
                      neutral=bool(comp.get("neutralSite")), detail=status.get("detail"),
                      home_record=home["record"], away_record=away["record"]),
        )
        if state == "final":
            rec["result"] = dict(home=home["score"], away=away["score"], detail=status.get("detail"))
            rec.setdefault("metrics", None)
        else:
            rec["result"] = None
            rec["metrics"] = None
        rec.setdefault("video", None)
        self.games[gid] = rec

    def period_for(self, ev: dict, page: dict, start: datetime):
        if self.cadence == "weekly":
            wk = int((ev.get("week") or page.get("week") or {}).get("number") or 0)
            return wk, f"week-{wk:02d}", f"Week {wk}"
        d = et_date(start)
        dt = datetime.fromisoformat(d)
        return d, d, dt.strftime("%b %-d")

    # ---------- metrics ----------
    def compute_metrics(self) -> int:
        """Fill metrics for final games that don't have them yet. Returns count computed."""
        todo = [g for g in self.games.values() if g["status"] == "final" and not g.get("metrics")]
        if not todo:
            return 0
        self.prepare_wp(todo)
        n = 0
        for g in todo:
            try:
                series = self.wp_series(g)
            except Exception as e:  # noqa: BLE001
                log(self.slug, "wp_series failed", g["id"], e)
                series = None
            if not series:
                continue
            wp, rem, is_ot = series
            g["metrics"] = raw_metrics(np.asarray(wp), np.asarray(rem), np.asarray(is_ot), self.reg_seconds)
            g["scored_at"] = utc_now().isoformat()
            n += 1
        save_json(self.games_path, self.games)
        return n

    def prepare_wp(self, todo: list[dict]) -> None:
        """Hook: bulk-load a season file once (NFL, CFB)."""

    def wp_series(self, g: dict):
        raise NotImplementedError

    # ---------- stakes ----------
    def compute_stakes(self) -> None:
        """Records entering each game from prior final results in the store (season to date)."""
        order = sorted(self.games.values(), key=lambda g: g["start_utc"])
        rec: dict[str, list[int]] = {}
        for g in order:
            h, a = g["home"]["id"], g["away"]["id"]
            hr, ar = tuple(rec.get(h, [0, 0, 0])), tuple(rec.get(a, [0, 0, 0]))
            extra = self.extra_stakes(g)
            g["stakes"] = dict(
                score=stakes_score(hr, ar, division=extra.get("division", False), rivalry=extra.get("rivalry", 0),
                                   ranked_bonus=extra.get("ranked_bonus", 0.0)),
                home_rec=rec_str(hr), away_rec=rec_str(ar), **{k: v for k, v in extra.items() if k not in ("ranked_bonus",)},
            )
            if g["status"] == "final" and g.get("result"):
                hs, as_ = g["result"]["home"], g["result"]["away"]
                rec.setdefault(h, [0, 0, 0]); rec.setdefault(a, [0, 0, 0])
                if hs > as_:
                    rec[h][0] += 1; rec[a][1] += 1
                elif as_ > hs:
                    rec[a][0] += 1; rec[h][1] += 1
                else:
                    rec[h][2] += 1; rec[a][2] += 1
        save_json(self.games_path, self.games)

    def extra_stakes(self, g: dict) -> dict:
        return {}

    # ---------- orchestration ----------
    def update(self) -> None:
        log(self.slug, "syncing schedule")
        self.sync_schedule()
        n = self.compute_metrics()
        log(self.slug, f"scored {n} new games; store has {len(self.games)} games")
        self.compute_stakes()

    # ---------- helpers for subclasses ----------
    @staticmethod
    def finalize_series(wp: list[float], rem: list[float], ot: list[bool], home_won: bool | None):
        """Append the terminal state so the last swing (OT winner, walk-off) is always counted."""
        if home_won is not None:
            wp.append(1.0 if home_won else 0.0)
            rem.append(0.0)
            ot.append(ot[-1] if ot else False)
        return wp, rem, ot
