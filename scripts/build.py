"""Build entry point: update every league's store, assign highlights, render the site.

    python scripts/build.py                # all leagues
    python scripts/build.py nfl nhl        # a subset
    python scripts/build.py --render-only  # skip network, just render from data/
"""
from __future__ import annotations

import sys
import traceback

sys.path.insert(0, __import__("os").path.dirname(__file__))

from common import log  # noqa: E402
from highlights import api_key, assign_videos  # noqa: E402
from leagues import LEAGUES  # noqa: E402
from render import render_site  # noqa: E402


def main(argv: list[str]) -> int:
    render_only = "--render-only" in argv
    slugs = [a for a in argv if a in LEAGUES] or list(LEAGUES)
    leagues = []
    for slug in LEAGUES:
        lg = LEAGUES[slug]()
        leagues.append(lg)
        if render_only or slug not in slugs:
            continue
        try:
            lg.update()
            n = assign_videos(lg, api_key())
            log(slug, f"videos assigned: {n}")
        except Exception:  # noqa: BLE001
            log(slug, "UPDATE FAILED")
            traceback.print_exc()
    render_site(leagues)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
