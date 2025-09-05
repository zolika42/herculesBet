# src/herculesbet/generate_picks.py
from __future__ import annotations

import os
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_engine, SessionLocal


# ---- Konfiguráció környezeti változókból (ésszerű defaultokkal) ----------------

EDGE_MIN = float(os.getenv("MIN_EDGE", "0.02"))            # minimum elvárt edge
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))  # Kelly-szorzó
LOOKBACK_HOURS = int(os.getenv("ODDS_LOOKBACK_HOURS", "48")) # visszatekintés oddsra
UPCOMING_ONLY = os.getenv("UPCOMING_ONLY", "true").lower() in ("1", "true", "yes")
UPCOMING_GRACE_MIN = int(os.getenv("UPCOMING_GRACE_MIN", "15"))  # kezdés után meddig játszható


# ---- Mag a beszúráshoz: közvetlenül edge_picks-be írunk -------------------------

SQL_INSERT_EDGEPICKS = text(
    f"""
WITH last_run AS (
    SELECT MAX(id) AS rid
    FROM model_runs
),
upcoming AS (
    SELECT m.id AS match_id
    FROM matches m
    {"WHERE m.start_time > now() - interval '{UPCOMING_GRACE_MIN} minutes'" if UPCOMING_ONLY else ""}
),
best_odds AS (
    -- A legjobb elérhető odds + a hozzá tartozó bookmaker a lookback ablakból
    SELECT DISTINCT ON (o.match_id, o.selection)
        o.match_id,
        o.selection,
        o.bookmaker_id,
        o.odds AS offered_odds
    FROM odds_snapshots o
    WHERE o.captured_at > now() - interval '{LOOKBACK_HOURS} hours'
      AND o.market IN ('1X2', 'h2h')
    ORDER BY o.match_id, o.selection, o.odds DESC, o.captured_at DESC
),
probs AS (
    SELECT
        p.model_run_id,
        p.match_id,
        COALESCE(p.market, '1X2') AS market,
        p.selection,
        p.prob,
        p.fair_odds
    FROM probabilities p, last_run
    WHERE p.model_run_id = last_run.rid
      AND p.market IN ('1X2','h2h')
),
candidates AS (
    SELECT
        pr.match_id,
        pr.market,
        pr.selection,
        bo.bookmaker_id,
        bo.offered_odds,
        pr.prob,
        pr.fair_odds,
        (bo.offered_odds * pr.prob - 1.0) AS edge_raw
    FROM probs pr
    JOIN best_odds bo USING (match_id, selection)
    {"JOIN upcoming u ON u.match_id = pr.match_id" if UPCOMING_ONLY else ""}
)
INSERT INTO edge_picks
    (match_id, market, selection, bookmaker_id,
     offered_odds, model_prob, edge, stake_fraction,
     created_at, status)
SELECT
    c.match_id,
    c.market,
    c.selection,
    COALESCE(c.bookmaker_id, (SELECT MIN(id) FROM bookmakers)),  -- fallback, ha valamiért nincs BM
    c.offered_odds,
    c.prob AS model_prob,
    c.edge_raw AS edge,
    GREATEST(0, LEAST(1, :kelly * (c.edge_raw / NULLIF(c.offered_odds - 1.0, 0)))) AS stake_fraction,
    now(),
    'open'
FROM candidates c
WHERE c.edge_raw >= :edge_min
  AND c.offered_odds > 1.0
  AND NOT EXISTS (
      SELECT 1
      FROM edge_picks ep
      WHERE ep.match_id = c.match_id
        AND ep.market   = c.market
        AND ep.selection = c.selection
        AND ep.status   = 'open'
  )
RETURNING
    match_id, market, selection, bookmaker_id,
    offered_odds, model_prob, edge, stake_fraction, created_at;
"""
)


def run_once(session: Session) -> int:
    """
    Beszúrja a friss edge pickeket közvetlenül az edge_picks táblába.
    Visszaadja a beszúrt sorok számát.
    """
    res = session.execute(
        SQL_INSERT_EDGEPICKS,
        {
            "kelly": KELLY_FRACTION,
            "edge_min": EDGE_MIN,
        },
    )
    rows = res.fetchall()
    return len(rows)


def main() -> None:
    engine = get_engine()
    inserted = 0
    with SessionLocal(bind=engine) as session:
        with session.begin():
            inserted = run_once(session)

    print(f"✔ Picks upsert done (inserted ~{inserted} rows)")


if __name__ == "__main__":
    main()

