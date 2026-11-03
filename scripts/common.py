"""Shared helpers: HTTP with light caching, ESPN endpoints, dates, JSON stores."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"          # downloads, git-ignored
SITE = ROOT / "site"        # generated, git-ignored
TEMPLATES = ROOT / "templates"

ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "wortha.watch build (github.com/perkinskit/wortha-watch)"}
ESPN = "https://site.api.espn.com/apis/site/v2/sports"

_session = requests.Session()
_session.headers.update(UA)


def log(*args):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *args, flush=True)


def get_json(url: str, params: dict | None = None, retries: int = 3, pause: float = 0.25) -> dict:
    """GET JSON with small retry/backoff. ESPN is unofficial; be polite."""
    last = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=60)
            if r.status_code == 200:
                time.sleep(pause)
                return r.json()
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:  # noqa: PERF203
            last = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def download(url: str, dest: Path, max_age_s: int = 0) -> Path:
    """Download to dest unless a fresh-enough copy exists."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and max_age_s and time.time() - dest.stat().st_mtime < max_age_s:
        return dest
    with _session.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.replace(dest)
    return dest


def espn(path: str, **params) -> dict:
    return get_json(f"{ESPN}/{path}", params=params or None)


def load_json(path: Path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    tmp.replace(path)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_espn_date(s: str) -> datetime:
    """ESPN gives '2026-11-01T17:00Z'."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def et_date(dt: datetime) -> str:
    return dt.astimezone(ET).strftime("%Y-%m-%d")


def et_time_label(dt: datetime) -> str:
    local = dt.astimezone(ET)
    return local.strftime("%-I:%M %p ET") if local.minute else local.strftime("%-I %p ET")


def day_label(dt: datetime) -> str:
    return dt.astimezone(ET).strftime("%a")


def clock_to_seconds(display: str) -> float:
    """'11:39' -> 699, '0:45.3' -> 45.3, '12:00' -> 720."""
    if not display:
        return 0.0
    parts = display.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except ValueError:
        return 0.0


def hex_color(s: str | None, fallback: str) -> str:
    s = (s or "").strip().lstrip("#")
    return f"#{s}" if len(s) == 6 else fallback
