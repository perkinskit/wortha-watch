# wortha-watch

Static site (Netlify, https://wortha.watch) ranking NFL / CFB / NBA / NHL games by an excitement index
computed from per-play win probability. Spoiler-free is the product: no page may ever show a final
score, winner, margin, or whether a game went to overtime. Highlight links only come from the league's
official YouTube channel and titles that mention an outcome are rejected (`scripts/highlights.py`).

Layout: `scripts/` (build.py entry, scoring.py shared math, leagues/<slug>.py per league, render.py,
highlights.py), `templates/` (Jinja), `data/<league>/<season>/games.json` (committed store; final
scores live here for records and must stay out of templates), `site/` (generated, git-ignored).

Run `python scripts/build.py --render-only` to rebuild pages from the store without network. The GitHub
Actions workflow commits `data/` and deploys `site/` (and `netlify/functions/`) with the Netlify CLI;
Netlify is NOT watching the repo. The hourly trigger is the Netlify scheduled function
`trigger-build.mts` (GitHub's cron alone skipped ~80% of runs). Pushes touching `scripts/`, `templates/` or `netlify.toml` also trigger a build.

When changing templates, grep the rendered `site/` for `\d{2}[-–]\d{2}` and outcome words before
deploying. Team colors come from ESPN (`data/<league>/teams.json`); don't add logos.
