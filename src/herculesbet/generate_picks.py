import os
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from .db import SessionLocal, get_engine
from .models import Match, OddsSnapshot, Probability, EdgePick, Bookmaker
from .utils.prob import remove_overround_1x2
from .utils.kelly import fractional_kelly
from .config import MIN_EDGE, KELLY_FRACTION, IMPROVE_THRESHOLD

def _best_1x2_odds_with_bookie(db: Session, match_id: int):
    """
    Visszaadja a legjobb (odds, bookmaker_id) párost mindhárom selectionre.
    """
    rows = (
        db.query(OddsSnapshot.selection,
                 func.max(OddsSnapshot.odds).label("best_odds"))
        .filter(OddsSnapshot.match_id == match_id,
                OddsSnapshot.market == "1X2")
        .group_by(OddsSnapshot.selection)
        .all()
    )
    if len(rows) != 3:
        return None
    # keressük meg, melyik bukitól jön a best_odds
    out = {}
    for sel, best in rows:
        rec = (
            db.query(OddsSnapshot.bookmaker_id, OddsSnapshot.odds)
            .filter(OddsSnapshot.match_id == match_id,
                    OddsSnapshot.market == "1X2",
                    OddsSnapshot.selection == sel,
                    OddsSnapshot.odds == best)
            .order_by(desc(OddsSnapshot.captured_at))  # ha több azonos, a legfrissebb
            .first()
        )
        out[sel] = {"odds": float(best), "bookmaker_id": int(rec[0]) if rec else 1}
    return out

def _latest_pick_edge(db: Session, match_id: int, selection: str) -> float | None:
    row = (
        db.query(EdgePick.edge)
        .filter(EdgePick.match_id == match_id, EdgePick.selection == selection)
        .order_by(desc(EdgePick.created_at))
        .first()
    )
    return float(row[0]) if row else None

def main():
    db: Session = SessionLocal()

    latest_run_id = (
        db.query(Probability.model_run_id)
        .order_by(Probability.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    match_ids = [
        mid for (mid,) in db.query(Probability.match_id)
        .filter(Probability.model_run_id == latest_run_id)
        .group_by(Probability.match_id).all()
    ]

    created = 0
    skipped = 0

    for mid in match_ids:
        probs = {p.selection: p.prob for p in db.query(Probability).filter_by(match_id=mid).all()}
        if set(probs) != {"H","D","A"}:
            continue

        best = _best_1x2_odds_with_bookie(db, mid)
        if not best:
            continue

        # implied (overround eltávolítva)
        p_b_h, p_b_d, p_b_a = remove_overround_1x2((best["H"]["odds"], best["D"]["odds"], best["A"]["odds"]))
        p_book = {"H": p_b_h, "D": p_b_d, "A": p_b_a}

        # legnagyobb edge-ű selection
        best_sel, best_edge = None, -1e9
        for sel in ("H","D","A"):
            edge = (probs[sel] - p_book[sel]) / max(p_book[sel], 1e-9)
            if edge > best_edge:
                best_edge, best_sel = edge, sel

        if best_edge < MIN_EDGE:
            continue

        # dup-szűrés
        prev = (
            db.query(EdgePick.edge)
            .filter(EdgePick.match_id == mid, EdgePick.selection == best_sel)
            .order_by(desc(EdgePick.created_at))
            .first()
        )
        if prev and (best_edge - float(prev[0])) < IMPROVE_THRESHOLD:
            skipped += 1
            continue

        offered = best[best_sel]["odds"]
        bkid = best[best_sel]["bookmaker_id"]
        stake_frac = fractional_kelly(probs[best_sel], offered, fraction=KELLY_FRACTION)

        ep = EdgePick(
            match_id=mid, market="1X2", selection=best_sel,
            bookmaker_id=bkid, offered_odds=offered,
            model_prob=probs[best_sel], edge=best_edge,
            stake_fraction=stake_frac,
        )
        db.add(ep); created += 1

    db.commit(); db.close()
    print(f"✔ picks created: {created} (skipped: {skipped})")

def insert_picks_from_probs():
    edge_min = float(os.getenv("MIN_EDGE", "0.02"))
    kelly = float(os.getenv("KELLY_FRACTION", "0.25"))
    bankroll = float(os.getenv("BANKROLL_UNITS", "1.0"))  # tartsd env-ben, ha szeretnéd

    sql = f"""
    WITH last_run AS (
      SELECT MAX(id) AS rid FROM model_runs
    ),
    best_odds AS (
      SELECT match_id, selection, MAX(odds) AS offered_odds
      FROM odds_snapshots
      WHERE captured_at > now() - interval '48 hours'
        AND market IN ('1X2','h2h')
      GROUP BY match_id, selection
    ),
    probs AS (
      SELECT p.model_run_id, p.match_id, p.market, p.selection, p.prob, p.fair_odds
      FROM probabilities p, last_run
      WHERE p.model_run_id = rid AND p.market IN ('1X2','h2h')
    ),
    candidates AS (
      SELECT pr.model_run_id,
             pr.match_id,
             COALESCE(pr.market,'1X2') AS market,
             pr.selection,
             pr.prob,
             pr.fair_odds,
             bo.offered_odds,
             (bo.offered_odds * pr.prob - 1.0) AS edge_raw
      FROM probs pr
      JOIN best_odds bo USING (match_id, selection)
    )
    INSERT INTO picks (match_id, model_run_id, market, selection,
                       prob, fair_odds, offered_odds, edge, kelly_frac, stake_units, created_at)
    SELECT c.match_id,
           c.model_run_id,
           c.market,
           c.selection,
           c.prob,
           c.fair_odds,
           c.offered_odds,
           c.edge_raw AS edge,
           GREATEST(0, LEAST(1, {kelly} * (c.edge_raw / NULLIF(c.offered_odds - 1.0,0)))) AS kelly_frac,
           ({bankroll} * GREATEST(0, LEAST(1, {kelly} * (c.edge_raw / NULLIF(c.offered_odds - 1.0,0))))) AS stake_units,
           now()
    FROM candidates c
    WHERE c.edge_raw >= {edge_min}
      AND c.offered_odds > 1.0
    ON CONFLICT DO NOTHING;
    """
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text(sql))
    return res.rowcount if hasattr(res, "rowcount") else None

if __name__ == "__main__":
    # ... a meglévő kód után:
    try:
        n = insert_picks_from_probs()
        print(f"✔ Picks upsert done (inserted ~{n} rows)")
    except Exception as e:
        print(f"[WARN] picks insert skipped with error: {e}")

