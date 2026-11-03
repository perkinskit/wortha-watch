"""Render the static site from each league's store. Nothing here ever emits a final score."""
from __future__ import annotations

import shutil
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import ET, SITE, TEMPLATES, log, utc_now
from scoring import percentile_scores

env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)

STATUS_ORDER = {"scored": 0, "unscored": 1, "live": 2, "pending": 3}


def row_for(g: dict, league) -> dict:
    """Public-safe projection of a game record. No result fields pass through."""
    st = g["stakes"] if g.get("stakes") else {}
    status = "scored" if g.get("metrics") and g.get("index") is not None else ("unscored" if g["status"] == "final" else g["status"])
    flags = []
    if st.get("division") and league.slug == "nfl":
        flags.append("division")
    if st.get("conference") and league.slug == "cfb":
        flags.append("conference")
    if st.get("rivalry"):
        flags.append("rivalry")
    recs = f"{st.get('away_rec', '')} at {st.get('home_rec', '')}" if st else ""
    when = g["labels"]["day"] if league.cadence == "weekly" else g["labels"]["time"]
    if league.cadence == "weekly" and g["labels"]["day"] in ("Sun", "Mon", "Thu") and "PM" in g["labels"]["time"]:
        hour = int(g["labels"]["time"].split(":")[0].split()[0])
        if hour >= 8 or (g["labels"]["day"] in ("Mon", "Thu")):
            when = f"{g['labels']['day']} night"
    espn = g.get("espn") or {}
    def rank_prefix(side):
        r = espn.get(f"{side}_rank")
        return f"#{r} " if league.slug == "cfb" and r and r <= 25 else ""
    return dict(
        id=g["id"], status=status, index=round(g["index"]) if status == "scored" else None,
        game=round(g["game_score"]) if status == "scored" else None,
        stakes=round(st["score"]) if st else None,
        season_rank=g.get("season_rank"), season_size=g.get("season_size"),
        away=g["away"], home=g["home"], away_rank=rank_prefix("away"), home_rank=rank_prefix("home"),
        matchup=f"{rank_prefix('away')}{g['away']['abbr']} @ {rank_prefix('home')}{g['home']['abbr']}",
        when=when, recs=recs, flags=flags, video=(g.get("video") or {}).get("id"),
        start_utc=g["start_utc"], period=g["period"], period_label=g["period_label"], period_sort=g["period_sort"],
    )


def period_rows(games: list[dict], league, period: str) -> list[dict]:
    rows = [row_for(g, league) for g in games if g["period"] == period]
    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], -(r["index"] or 0), r["start_utc"]))
    for i, r in enumerate([r for r in rows if r["status"] == "scored"], 1):
        r["rank"] = i
    return rows


def league_context(league) -> dict:
    games = list(league.games.values())
    percentile_scores(games)
    periods = {}
    for g in games:
        p = periods.setdefault(g["period"], dict(key=g["period"], label=g["period_label"], sort=g["period_sort"], n=0, scored=0, pending=0))
        p["n"] += 1
        if g.get("index") is not None:
            p["scored"] += 1
        elif g["status"] != "final":
            p["pending"] += 1
    ordered = sorted(periods.values(), key=lambda p: p["sort"])
    with_scores = [p for p in ordered if p["scored"]]
    current = with_scores[-1]["key"] if with_scores else (ordered[-1]["key"] if ordered else None)
    season_rows = sorted([row_for(g, league) for g in games if g.get("index") is not None], key=lambda r: -r["index"])[:25]
    for i, r in enumerate(season_rows, 1):
        r["rank"] = i
    for p in ordered:
        best = max([g for g in games if g["period"] == p["key"] and g.get("index") is not None], key=lambda g: g["index"], default=None)
        p["top"] = row_for(best, league) if best else None
    return dict(league=league, periods=ordered, current=current, season_rows=season_rows,
                scored_total=sum(1 for g in games if g.get("index") is not None))


def render_site(leagues: list) -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    built_at = utc_now().astimezone(ET).strftime("%a %b %-d, %-I:%M %p ET")
    common = dict(built_at=built_at, leagues=leagues, year=utc_now().year)

    def write(path: str, template: str, **ctx):
        out = SITE / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(env.get_template(template).render(**common, **ctx))

    landing = []
    for lg in leagues:
        ctx = league_context(lg)
        cur = ctx["current"]
        periods = {p["key"]: p for p in ctx["periods"]}
        for key, p in periods.items():
            rows = period_rows(list(lg.games.values()), lg, key)
            idx = ctx["periods"].index(p)
            prev_p = ctx["periods"][idx - 1] if idx > 0 else None
            next_p = ctx["periods"][idx + 1] if idx + 1 < len(ctx["periods"]) else None
            page = dict(league=lg, period=p, rows=rows, prev=prev_p, next=next_p, is_current=(key == cur),
                        scored_total=ctx["scored_total"])
            write(f"{lg.slug}/{key}/index.html", "league.html", **page)
            if key == cur:
                write(f"{lg.slug}/index.html", "league.html", **page)
                landing.append(dict(league=lg, period=p, rows=[r for r in rows if r["status"] == "scored"][:3],
                                    pending=sum(1 for r in rows if r["status"] in ("pending", "live"))))
        write(f"{lg.slug}/season/index.html", "season.html", league=lg, rows=ctx["season_rows"], scored_total=ctx["scored_total"])
        write(f"{lg.slug}/archive/index.html", "archive.html", league=lg, periods=list(reversed(ctx["periods"])))
        if not cur:
            write(f"{lg.slug}/index.html", "league.html", league=lg, period=None, rows=[], prev=None, next=None, is_current=True, scored_total=0)
    write("index.html", "index.html", cards=landing)
    write("methods/index.html", "methods.html")
    write("subscribed/index.html", "subscribed.html")
    write("404.html", "404.html")
    log("rendered site:", sum(1 for _ in SITE.rglob("*.html")), "pages")
