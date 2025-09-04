from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from .db import SessionLocal
from .models import Match, OddsSnapshot, EdgePick, BankrollLog

def _match_result(m: Match) -> str | None:
    if m.home_score is None or m.away_score is None:
        return None
    if m.home_score > m.away_score:
        return "H"
    if m.home_score < m.away_score:
        return "A"
    return "D"

def _closing_odds(db: Session, match_id: int, selection: str, bookmaker_id: int) -> float | None:
    row = (
        db.query(func.max(OddsSnapshot.captured_at))
        .filter(OddsSnapshot.match_id == match_id,
                OddsSnapshot.bookmaker_id == bookmaker_id,     # <-- EZ ÚJ
                OddsSnapshot.market == "1X2",
                OddsSnapshot.selection == selection)
        .one()
    )
    last_ts = row[0]
    if not last_ts:
        return None
    o = (
        db.query(OddsSnapshot.odds)
        .filter(OddsSnapshot.match_id == match_id,
                OddsSnapshot.bookmaker_id == bookmaker_id,     # <-- EZ ÚJ
                OddsSnapshot.market == "1X2",
                OddsSnapshot.selection == selection,
                OddsSnapshot.captured_at == last_ts)
        .scalar()
    )
    return float(o) if o is not None else None

def settle_finished_matches(db: Session, starting_bankroll: float | None = None):
    """
    Az összes 'proposed' vagy 'placed' picket lezárja, ha a meccs 'finished'.
    Számolja: result, profit, closing_odds, CLV, és opcionálisan bankroll logot frissít.
    CLV = (offered_odds - closing_odds) / closing_odds
    """
    # gyűjtsük ki azokat a pickeket, ahol a match finished
    rows = (
        db.query(EdgePick, Match)
        .join(Match, EdgePick.match_id == Match.id)
        .filter(Match.status == "finished",
                EdgePick.status.in_(["proposed", "placed"]))
        .all()
    )
    settled = 0
    total_profit = 0.0

    for ep, m in rows:
        res = _match_result(m)
        if not res:
            continue

        ep.status = "settled"
        if res == ep.selection:
            # win -> profit = stake * (odds - 1)
            # stake_fraction a bankroll %-a volt; settlementkor nincs tényleges BR, így jelképesen 1.0 egység BR-rel számolunk,
            # a "profit" mezőt HUF-ban tartjuk általában tényleges tétek alapján. Itt egyszerűsítünk:
            # ha valódi téttel dolgozunk, a bet placementnél kell eltárolni a HUF összeget is.
            # Most: "egység-bankroll" feltételezéssel:
            profit = ep.stake_fraction * (ep.offered_odds - 1.0)
            ep.profit = profit
            ep.result = "win"
        else:
            profit = -ep.stake_fraction
            ep.profit = profit
            ep.result = "loss"

        co = _closing_odds(db, ep.match_id, ep.selection, ep.bookmaker_id)
        ep.closing_odds = co
        if co:
            ep.clv = (ep.offered_odds - co) / co

        total_profit += profit
        settled += 1

    # opcionális bankroll log
    if starting_bankroll is not None and settled:
        latest = db.query(BankrollLog).order_by(BankrollLog.at.desc()).first()
        current = latest.bankroll if latest else starting_bankroll
        current += total_profit * current  # egység-bankroll modell -> arányosítva
        db.add(BankrollLog(at=datetime.utcnow(), bankroll=current))

    db.commit()
    return settled

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--starting-bankroll", type=float, default=None,
                    help="Ha megadod, bankroll log is frissül (egység-modell).")
    args = ap.parse_args()
    db = SessionLocal()
    n = settle_finished_matches(db, args.starting_bankroll)
    db.close()
    print(f"✔ settled picks: {n}")

if __name__ == "__main__":
    main()

