from fastapi import FastAPI
from sqlalchemy.orm import Session, aliased
from .db import SessionLocal
from .models import EdgePick, Match, Team, League, Bookmaker

app = FastAPI(title="HerculesBet API v0.1")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/picks")
def picks(limit: int = 50):
    db: Session = SessionLocal()
    try:
        Home = aliased(Team)
        Away = aliased(Team)

        rows = (
            db.query(EdgePick, Match, Home, Away, League, Bookmaker)
            .join(Match, EdgePick.match_id == Match.id)
            .join(Home, Match.home_team_id == Home.id)
            .join(Away, Match.away_team_id == Away.id)
            .join(League, Match.league_id == League.id)
            .join(Bookmaker, EdgePick.bookmaker_id == Bookmaker.id)
            .order_by(EdgePick.created_at.desc())
            .limit(limit)
            .all()
        )

        out = []
        for ep, m, home, away, league, bk in rows:   # <-- 6 elem!
            out.append({
                "match_id": m.id,
                "league": league.name,
                "home": home.name,
                "away": away.name,
                "start_time": m.start_time.isoformat(),
                "selection": ep.selection,
                "bookmaker": bk.name,               # <-- új mező
                "odds": ep.offered_odds,
                "p_model": ep.model_prob,
                "edge": ep.edge,
                "stake_fraction": ep.stake_fraction,
                "created_at": ep.created_at.isoformat(),
                "status": ep.status,
                "result": ep.result,
                "profit": ep.profit,
                "closing_odds": ep.closing_odds,
                "clv": ep.clv,
            })
        return out
    finally:
        db.close()

from sqlalchemy import func

@app.get("/stats/summary")
def stats_summary():
    db = SessionLocal()
    try:
        total = db.query(func.count()).select_from(EdgePick).scalar() or 0
        settled = db.query(func.count()).select_from(
            db.query(EdgePick).filter(EdgePick.status=="settled").subquery()
        ).scalar() or 0
        wins = db.query(func.count()).select_from(
            db.query(EdgePick).filter(EdgePick.status=="settled", EdgePick.result=="win").subquery()
        ).scalar() or 0

        # egység-bankroll profit (összegzett 'profit' arány)
        profit_sum = db.query(func.coalesce(func.sum(EdgePick.profit), 0.0))\
            .filter(EdgePick.status=="settled").scalar() or 0.0

        avg_edge = db.query(func.avg(EdgePick.edge)).scalar() or 0.0
        avg_clv  = db.query(func.avg(EdgePick.clv)).filter(EdgePick.clv != None).scalar()
        return {
            "picks_total": total,
            "picks_settled": settled,
            "wins": wins,
            "hit_rate": (wins/settled) if settled else None,
            "profit_sum_units": profit_sum,
            "avg_edge": avg_edge,
            "avg_clv": avg_clv,
        }
    finally:
        db.close()

