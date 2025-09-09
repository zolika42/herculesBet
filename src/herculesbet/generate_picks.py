# src/herculesbet/generate_picks.py
import os
from typing import Optional

from sqlalchemy import text
from .db import SessionLocal

# -----------------------------
# Env paramok
# -----------------------------
def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default

def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default

def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    v = val.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default

EDGE_MIN = _get_float("MIN_EDGE", 0.02)
KELLY_FRACTION = _get_float("KELLY_FRACTION", 0.25)
UPCOMING_ONLY = _get_bool("UPCOMING_ONLY", True)
UPCOMING_GRACE_MIN = _get_int("UPCOMING_GRACE_MIN", 15)   # meccs kezdéséhez képest ennyivel “hátra” még ok
LOOKBACK_HOURS = _get_int("LOOKBACK_HOURS", 48)           # odds snapshot lookback ablak

# -----------------------------
# SQL (bind paramokkal!)
# -----------------------------
# 1) UPDATE meglévő OPEN rekordok
SQL_UPDATE_OPEN = text("""
WITH last_run AS (
  SELECT MAX(id) AS rid FROM model_runs
),
upcoming AS (
  SELECT m.id AS match_id
  FROM matches m
  WHERE (:upcoming_only = FALSE)
     OR (m.start_time > now() - make_interval(mins => :grace_min))
),
best_odds AS (
  SELECT DISTINCT ON (o.match_id, o.selection)
    o.match_id, o.selection, o.bookmaker_id, o.odds AS offered_odds
  FROM odds_snapshots o
  WHERE o.captured_at > now() - make_interval(hours => :lookback_hours)
    AND o.market IN ('1X2','h2h')
  ORDER BY o.match_id, o.selection, o.odds DESC, o.captured_at DESC
),
probs AS (
  SELECT p.model_run_id, p.match_id,
         COALESCE(p.market,'1X2') AS market, p.selection, p.prob, p.fair_odds
  FROM probabilities p, last_run
  WHERE p.model_run_id = last_run.rid
    AND p.market IN ('1X2','h2h')
),
candidates AS (
  SELECT pr.match_id, pr.market, pr.selection,
         bo.bookmaker_id, bo.offered_odds,
         pr.prob, pr.fair_odds,
         (bo.offered_odds * pr.prob - 1.0) AS edge_raw
  FROM probs pr
  JOIN best_odds bo USING (match_id, selection)
  JOIN upcoming u ON u.match_id = pr.match_id
)
UPDATE edge_picks ep
SET bookmaker_id = c.bookmaker_id,
    offered_odds = c.offered_odds,
    model_prob   = c.prob,
    edge         = c.edge_raw,
    stake_fraction = GREATEST(0, LEAST(1, :kelly * (c.edge_raw / NULLIF(c.offered_odds - 1.0, 0)))),
    created_at   = now()
FROM candidates c
WHERE ep.status = 'open'
  AND ep.match_id  = c.match_id
  AND ep.market    = c.market
  AND ep.selection = c.selection
  AND c.edge_raw >= :edge_min
  AND c.offered_odds > 1.0;
""")

# 2) INSERT csak ami még nem létezik OPEN-ként
SQL_INSERT_NEW = text("""
WITH last_run AS (
  SELECT MAX(id) AS rid FROM model_runs
),
upcoming AS (
  SELECT m.id AS match_id
  FROM matches m
  WHERE (:upcoming_only = FALSE)
     OR (m.start_time > now() - make_interval(mins => :grace_min))
),
best_odds AS (
  SELECT DISTINCT ON (o.match_id, o.selection)
    o.match_id, o.selection, o.bookmaker_id, o.odds AS offered_odds
  FROM odds_snapshots o
  WHERE o.captured_at > now() - make_interval(hours => :lookback_hours)
    AND o.market IN ('1X2','h2h')
  ORDER BY o.match_id, o.selection, o.odds DESC, o.captured_at DESC
),
probs AS (
  SELECT p.model_run_id, p.match_id,
         COALESCE(p.market,'1X2') AS market, p.selection, p.prob, p.fair_odds
  FROM probabilities p, last_run
  WHERE p.model_run_id = last_run.rid
    AND p.market IN ('1X2','h2h')
),
candidates AS (
  SELECT pr.match_id, pr.market, pr.selection,
         bo.bookmaker_id, bo.offered_odds,
         pr.prob, pr.fair_odds,
         (bo.offered_odds * pr.prob - 1.0) AS edge_raw
  FROM probs pr
  JOIN best_odds bo USING (match_id, selection)
  JOIN upcoming u ON u.match_id = pr.match_id
)
INSERT INTO edge_picks
  (match_id, market, selection, bookmaker_id,
   offered_odds, model_prob, edge, stake_fraction,
   created_at, status)
SELECT
  c.match_id, c.market, c.selection,
  COALESCE(c.bookmaker_id, (SELECT MIN(id) FROM bookmakers)),
  c.offered_odds, c.prob, c.edge_raw,
  GREATEST(0, LEAST(1, :kelly * (c.edge_raw / NULLIF(c.offered_odds - 1.0, 0)))),
  now(), 'open'
FROM candidates c
WHERE c.edge_raw >= :edge_min
  AND c.offered_odds > 1.0
  AND NOT EXISTS (
    SELECT 1 FROM edge_picks ep
    WHERE ep.status='open'
      AND ep.match_id  = c.match_id
      AND ep.market    = c.market
      AND ep.selection = c.selection
  )
RETURNING match_id;
""")

def run_once(session) -> int:
    params = {
        "kelly": KELLY_FRACTION,
        "edge_min": EDGE_MIN,
        "upcoming_only": UPCOMING_ONLY,
        "grace_min": UPCOMING_GRACE_MIN,
        "lookback_hours": LOOKBACK_HOURS,
    }
    # először frissítjük a meglévő OPEN rekordokat
    session.execute(SQL_UPDATE_OPEN, params)
    # majd beszúrjuk az újakat
    res = session.execute(SQL_INSERT_NEW, params)
    rows = res.fetchall()
    return len(rows)

def main():
    inserted = 0
    with SessionLocal() as session:
        inserted = run_once(session)
        session.commit()
    print(f"✔ Picks upsert done (inserted ~{inserted} rows)")

if __name__ == "__main__":
    main()
