# wortha.watch

Which games were worth watching, ranked by an excitement index computed from play-by-play win
probability. Spoiler-free: the site shows matchups and scores-of-excitement, never results.

Live at https://wortha.watch — NFL, college football, NBA, NHL.

## How it works

- `scripts/scoring.py` turns a per-play win-probability series into four components (volatility,
  drama, finish, competitiveness), percentile-ranks them against the league-season, and blends in a
  pregame stakes score. See `/methods/` on the site for the plain-English version.
- `scripts/leagues/` has one module per league: where its schedule and win probability come from
  (nflverse for the NFL, sportsdataverse/ESPN for college, ESPN for the NBA, and a Poisson goal model
  for the NHL), plus league-specific stakes (divisions, rivalries, rankings).
- `scripts/highlights.py` finds each game's official highlight video through the YouTube Data API,
  matching on team names and date and rejecting any title that gives away the result.
- `scripts/render.py` + `templates/` build the static site into `site/`.
- `data/<league>/<season>/games.json` is the store: every game's raw metrics, stakes inputs and video
  id, committed so each build is reproducible. Final scores live there too (they are needed for
  records) but never reach a page.

## Running

    pip install -r requirements.txt
    YOUTUBE_API_KEY=... python scripts/build.py          # all leagues
    python scripts/build.py nfl                          # one league
    python scripts/build.py --render-only                # no network

The GitHub Actions workflow commits data changes and deploys `site/` to Netlify with the CLI
(secrets: `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`, `YOUTUBE_API_KEY`). GitHub's own cron drops most
hourly runs, so `netlify/functions/trigger-build.mts` (a Netlify scheduled function) dispatches the
workflow every hour; it needs `GITHUB_DISPATCH_TOKEN` (fine-grained PAT, Actions: read & write) as a
Netlify environment variable with the Functions scope.

## Seeding a highlight by hand

Drop an entry in `data/<league>/<season>/video_seeds.json` keyed `"<period>|<AWAY>@<HOME>"` using ESPN
abbreviations, e.g. `"week-08|KC@DEN": "Tj71A_YItgE"`.
