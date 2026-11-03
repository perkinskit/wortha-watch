"""Excitement scoring from a win-probability series.

Every league produces, per game, a sequence of (home_wp, seconds_remaining_in_regulation, is_overtime)
sampled at each play. From that we compute four raw components:

  volatility   sum |dWP| per play, weighted 1x at the start rising to 2x at the final whistle, 2.2x in OT
  drama        sum dWP^2 with the same weights -> rewards sudden big plays over slow drift
  finish       how close to 50/50 WP sat over the last 5 minutes of regulation (and OT)
  competitive  share of plays with WP between 20% and 80%

Components are percentile-ranked against every completed game in the same league-season, then blended:
  game  = .45 volatility + .25 drama + .20 finish + .10 competitive          (0-100)
  index = .8 game + .2 stakes                                                 (0-100)
"""
from __future__ import annotations

import numpy as np

OT_WEIGHT = 2.2
LATE_SECONDS = 300
WEIGHTS = {"volatility": 0.45, "drama": 0.25, "finish": 0.20, "competitive": 0.10}
GAME_SHARE, STAKES_SHARE = 0.8, 0.2


def raw_metrics(wp: np.ndarray, rem: np.ndarray, is_ot: np.ndarray, reg_seconds: float) -> dict:
    """wp: home win prob per play (0..1). rem: seconds remaining in regulation at the play. is_ot: bool per play."""
    wp = np.clip(np.asarray(wp, dtype=float), 0, 1)
    rem = np.asarray(rem, dtype=float)
    is_ot = np.asarray(is_ot, dtype=bool)
    n = len(wp)
    if n < 2:
        return dict(volatility=0.0, drama=0.0, finish=0.0, competitive=0.0, max_swing=0.0, ot=bool(is_ot.any()), n_plays=n)
    frac = np.where(is_ot, 1.0, 1.0 - np.clip(rem, 0, reg_seconds) / reg_seconds)
    w = np.where(is_ot, OT_WEIGHT, 1.0 + frac)
    d = np.diff(wp)
    wd = w[1:]
    late = (rem <= LATE_SECONDS) | is_ot
    if not late.any():
        late = np.zeros(n, dtype=bool)
        late[-max(1, n // 10):] = True
    return dict(
        volatility=float(np.sum(np.abs(d) * wd)),
        drama=float(np.sum(d ** 2 * wd)),
        finish=float(np.mean(1.0 - np.abs(2 * wp[late] - 1))),
        competitive=float(np.mean((wp >= 0.2) & (wp <= 0.8))),
        max_swing=float(np.max(np.abs(d))),
        ot=bool(is_ot.any()),
        n_plays=int(n),
    )


def percentile_scores(games: list[dict]) -> None:
    """Mutates each final game dict: adds game_score, index, season_rank. Non-final games are skipped."""
    final = [g for g in games if g.get("status") == "final" and g.get("metrics")]
    if not final:
        return
    for comp in WEIGHTS:
        vals = np.array([g["metrics"][comp] for g in final])
        order = vals.argsort().argsort()  # rank 0..n-1, ties broken by order
        # average-rank percentiles so ties don't depend on insertion order
        ranks = np.empty(len(vals))
        sorted_idx = np.argsort(vals, kind="mergesort")
        sv = vals[sorted_idx]
        i = 0
        while i < len(sv):
            j = i
            while j + 1 < len(sv) and sv[j + 1] == sv[i]:
                j += 1
            ranks[sorted_idx[i:j + 1]] = (i + j) / 2 + 1
            i = j + 1
        pct = ranks / len(vals) * 100
        for g, p in zip(final, pct):
            g.setdefault("pct", {})[comp] = float(p)
        del order
    for g in final:
        g["game_score"] = sum(WEIGHTS[c] * g["pct"][c] for c in WEIGHTS)
        stakes = (g.get("stakes") or {}).get("score", 50.0)
        g["index"] = GAME_SHARE * g["game_score"] + STAKES_SHARE * stakes
    by_index = sorted(final, key=lambda g: -g["index"])
    for i, g in enumerate(by_index, 1):
        g["season_rank"] = i
    for g in final:
        g["season_size"] = len(final)


def stakes_score(home_rec: tuple[int, int, int], away_rec: tuple[int, int, int], *, division: bool = False,
                 rivalry: int = 0, ranked_bonus: float = 0.0) -> float:
    """Pregame stakes 0-100. Records are (w, l, t) entering the game."""
    def pct(r):
        w, l, t = r
        n = w + l + t
        return (w + 0.5 * t) / n if n else 0.5
    hp, ap = pct(home_rec), pct(away_rec)
    s = 60 * (hp + ap) / 2
    if hp >= 0.5 and ap >= 0.5:
        s += 15
    if division:
        s += 15
    s += rivalry + ranked_bonus
    return float(min(100.0, max(0.0, s)))


def rec_str(r: tuple[int, int, int]) -> str:
    w, l, t = r
    return f"{w}-{l}" + (f"-{t}" if t else "")
