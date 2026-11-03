"""Find official highlight videos on YouTube without ever showing a title on the site.

Strategy: read the league channel's uploads playlist through the YouTube Data API (1 quota unit per
50 videos), match a game by both team names plus its week or date, and reject any title that leaks
an outcome. Titles are used for matching only; the site stores just the video id.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

from common import DATA, ET, get_json, load_json, log, save_json

API = "https://www.googleapis.com/youtube/v3/playlistItems"
MAX_PAGES = 8
MAX_ATTEMPTS = 40          # hourly runs; stop looking after ~2 days

# Anything that reveals how the game went. Case-insensitive except the OT token.
SPOILER_WORDS = re.compile(
    r"\b(win|wins|won|winner|winners|beat|beats|defeat|defeats|defeated|upset|upsets|stun|stuns|stunned|"
    r"surviv\w*|comeback|rall(y|ies|ied)|clinch\w*|sweep\w*|blowout|dominat\w*|rout|edges?|escapes?|"
    r"shock\w*|overtime|shootout|walk-?off|buzzer|game-?winn\w*|thriller|crazy|insane|historic|"
    r"epic|collapse|choke|meltdown|final score)\b", re.I)
SPOILER_OT = re.compile(r"\bOT\b|\bSO\b")
SPOILER_SCORE = re.compile(r"\b\d{1,3}\s*[-–]\s*\d{1,3}\b")
SPOILER_RANK = re.compile(r"\bno\.?\s*\d{1,2}\b|#\d{1,2}\b", re.I)   # ranks are fine, but strip before score check


def spoils(title: str) -> bool:
    t = SPOILER_RANK.sub(" ", title)
    return bool(SPOILER_WORDS.search(t) or SPOILER_OT.search(t) or SPOILER_SCORE.search(t))


def uploads_playlist(channel_id: str) -> str:
    return "UU" + channel_id[2:]


def fetch_uploads(channel_id: str, api_key: str, max_pages: int = MAX_PAGES) -> list[dict]:
    items, token = [], None
    for _ in range(max_pages):
        params = dict(part="snippet", playlistId=uploads_playlist(channel_id), maxResults=50, key=api_key)
        if token:
            params["pageToken"] = token
        j = get_json(API, params=params, pause=0.1)
        for it in j.get("items", []):
            sn = it["snippet"]
            vid = (sn.get("resourceId") or {}).get("videoId")
            if vid:
                items.append(dict(id=vid, title=sn.get("title", ""), published=sn.get("publishedAt", "")))
        token = j.get("nextPageToken")
        if not token:
            break
    return items


def _has_team(title: str, team: dict) -> bool:
    t = title.lower()
    return team["name"].lower() in t or re.search(rf"\b{re.escape(team['nick'].lower())}\b", t) is not None


def matcher(league_slug: str, g: dict):
    """Return a predicate(title) for this game, league-specific title conventions."""
    home, away = g["home"], g["away"]
    start = datetime.fromisoformat(g["start_utc"]).astimezone(ET)
    if league_slug == "nfl":
        week = re.compile(rf"\bweek\s*{g['period_sort']}\b", re.I)
        def ok(title):
            tl = title.lower()
            return ("highlight" in tl and "preview" not in tl and "full game" not in tl and "recap" not in tl
                    and _has_team(title, home) and _has_team(title, away) and week.search(title))
        return ok
    if league_slug == "nhl":
        d = start.strftime("%b %-d, %Y")  # 'Nov 2, 2026'
        def ok(title):
            tl = title.lower()
            return ("highlights" in tl and d in title and _has_team(title, home) and _has_team(title, away)
                    and "condensed" not in tl and "recap" not in tl)
        return ok
    if league_slug == "nba":
        d = start.strftime("%B %-d, %Y")  # 'November 1, 2026'
        def ok(title):
            tl = title.lower()
            return ("full game highlights" in tl and d.lower() in tl and _has_team(title, home) and _has_team(title, away))
        return ok
    return lambda title: False


def assign_videos(league, api_key: str | None) -> int:
    """Fill `video` for final games lacking one. Returns number assigned."""
    games = league.games
    seeds = load_json(league.dir / "video_seeds.json", {})
    n = 0
    for g in games.values():
        if g.get("video") or g["status"] != "final":
            continue
        key = f"{g['period']}|{g['away']['abbr']}@{g['home']['abbr']}"
        if key in seeds:
            g["video"] = dict(id=seeds[key], source="seed")
            n += 1
    if not api_key or not league.youtube_channel:
        if n:
            save_json(league.games_path, games)
        return n
    cutoff = (datetime.now(timezone.utc) - timedelta(days=12)).isoformat()
    todo = [g for g in games.values() if g["status"] == "final" and not g.get("video")
            and g["start_utc"] >= cutoff and g.get("video_attempts", 0) < MAX_ATTEMPTS]
    if not todo:
        return n
    try:
        uploads = fetch_uploads(league.youtube_channel, api_key)
    except Exception as e:  # noqa: BLE001
        log(league.slug, "youtube fetch failed:", e)
        return n
    log(league.slug, f"youtube: scanned {len(uploads)} uploads for {len(todo)} games")
    for g in todo:
        ok = matcher(league.slug, g)
        hits = [u for u in uploads if ok(u["title"])]
        clean = [u for u in hits if not spoils(u["title"])]
        if clean:
            g["video"] = dict(id=clean[0]["id"], source="youtube", published=clean[0]["published"])
            n += 1
        else:
            g["video_attempts"] = g.get("video_attempts", 0) + 1
            if hits:
                g["video_rejected"] = len(hits)   # a title existed but would have spoiled
    save_json(league.games_path, games)
    return n


def api_key() -> str | None:
    return os.environ.get("YOUTUBE_API_KEY") or None
