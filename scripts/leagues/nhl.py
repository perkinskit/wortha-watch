"""NHL: schedule and plays from ESPN; win probability from a goal-based (Poisson) model.

No public per-play WP feed exists for hockey, so we build one:
  remaining goals for each side ~ Poisson(rate * minutes_left / 60)
  P(home wins) = P(lead + Xh - Xa > 0) + P(lead + Xh - Xa == 0) * q
where q is the home side's chance in OT/shootout. Pregame rates come from the betting line
(moneyline -> p0, over/under -> total goals), solved so the model's opening WP equals p0.
"""
from __future__ import annotations

from datetime import date
from math import exp

from common import clock_to_seconds, espn
from leagues.base import League

PERIOD_SECONDS = 1200.0
REG = 3 * PERIOD_SECONDS
DEFAULT_TOTAL = 6.0
MAX_GOALS = 12


def _pois(lam: float, k: int) -> float:
    p = exp(-lam)
    for i in range(1, k + 1):
        p *= lam / i
    return p


def home_wp(lead: int, secs_left: float, lam_h: float, lam_a: float, q: float) -> float:
    """Win probability for the home side with `lead` goals and `secs_left` of regulation."""
    th, ta = lam_h * secs_left / REG, lam_a * secs_left / REG
    ph = [_pois(th, k) for k in range(MAX_GOALS + 1)]
    pa = [_pois(ta, k) for k in range(MAX_GOALS + 1)]
    win = tie = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            d = lead + i - j
            if d > 0:
                win += ph[i] * pa[j]
            elif d == 0:
                tie += ph[i] * pa[j]
    return win + tie * q


def moneyline_to_prob(ml: float | None) -> float | None:
    if ml is None:
        return None
    ml = float(ml)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def solve_rates(p0: float, total: float, q: float) -> tuple[float, float]:
    """Find home/away scoring rates summing to `total` whose opening WP equals p0 (bisection on home share)."""
    lo, hi = 0.25, 0.75
    for _ in range(30):
        mid = (lo + hi) / 2
        if home_wp(0, REG, total * mid, total * (1 - mid), q) < p0:
            lo = mid
        else:
            hi = mid
    s = (lo + hi) / 2
    return total * s, total * (1 - s)


class NHL(League):
    slug = "nhl"
    name = "NHL"
    short = "NHL"
    cadence = "daily"
    reg_seconds = REG
    espn_path = "hockey/nhl"
    season = "2026-27"
    season_start = date(2026, 10, 7)
    youtube_channel = "UCqFMzb-4AUf6WAIbl132QKA"

    def wp_series(self, g):
        s = espn(f"{self.espn_path}/summary", event=g["id"])
        plays = s.get("plays") or []
        if len(plays) < 40:
            return None
        # pregame line
        p0, total = 0.54, DEFAULT_TOTAL
        for pc in s.get("pickcenter") or []:
            ph = moneyline_to_prob((pc.get("homeTeamOdds") or {}).get("moneyLine"))
            pa = moneyline_to_prob((pc.get("awayTeamOdds") or {}).get("moneyLine"))
            if ph and pa:
                p0 = ph / (ph + pa)  # strip the vig
            if pc.get("overUnder"):
                total = float(pc["overUnder"])
            break
        q = 0.5 + (p0 - 0.5) * 0.6  # OT/shootout edge, damped
        lam_h, lam_a = solve_rates(p0, total, q)
        wp, rem, ot = [], [], []
        last = None
        for p in plays:
            period = int((p.get("period") or {}).get("number") or 1)
            elapsed = clock_to_seconds((p.get("clock") or {}).get("displayValue", "0:00"))  # NHL clock counts up
            if period <= 3:
                left = max(0.0, REG - ((period - 1) * PERIOD_SECONDS + elapsed))
                lead = int(p.get("homeScore") or 0) - int(p.get("awayScore") or 0)
                w = home_wp(lead, left, lam_h, lam_a, q)
                is_ot = False
            else:
                left, is_ot = 0.0, True
                w = q  # tied going into OT; the goal itself is captured by the terminal state
            state = (round(w, 4), round(left), is_ot)
            if state == last:
                continue  # skip no-op events (faceoffs at the same second)
            last = state
            wp.append(w); rem.append(left); ot.append(is_ot)
        home_won = g["result"]["home"] > g["result"]["away"] if g.get("result") else None
        g["source"] = dict(wp="poisson-model", p0=round(p0, 3), total=total)
        return self.finalize_series(wp, rem, ot, home_won)
