# wortha.watch

Which games were worth watching, ranked by an excitement index computed from play-by-play win probability. Spoiler-free: the site shows matchups and scores, never results.

Leagues: NFL (live), college football, NBA, NHL (in progress).

## How it works
- `scripts/` scores every game in a season from play-by-play win probability (volatility, drama, finish, competitiveness, each percentile-ranked against the season) plus a pregame stakes component.
- A scheduled GitHub Actions job rebuilds `site/` during each league's game windows and deploys to Netlify.
- `data/` holds the generated scores and highlight IDs so every week is reproducible.
