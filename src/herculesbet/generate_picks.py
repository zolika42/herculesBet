from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from .db import SessionLocal
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

