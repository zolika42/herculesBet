from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import SessionLocal
from .models import League, Team, Match, Bookmaker, OddsSnapshot

def get_or_create_league(db: Session, name: str, country="HU", sport="football") -> League:
    obj = db.execute(select(League).where(League.name == name)).scalar_one_or_none()
    if obj: return obj
    obj = League(name=name, country=country, sport=sport)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def get_or_create_team(db: Session, league_id: int, name: str) -> Team:
    obj = db.execute(select(Team).where(Team.league_id==league_id, Team.name==name)).scalar_one_or_none()
    if obj: return obj
    obj = Team(league_id=league_id, name=name)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def get_or_create_bookmaker(db: Session, name: str) -> Bookmaker:
    obj = db.execute(select(Bookmaker).where(Bookmaker.name==name)).scalar_one_or_none()
    if obj: return obj
    obj = Bookmaker(name=name)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def add_match(db: Session, league_name: str, home: str, away: str, start_iso: str) -> Match:
    league = get_or_create_league(db, league_name)
    t_home = get_or_create_team(db, league.id, home)
    t_away = get_or_create_team(db, league.id, away)
    start = datetime.fromisoformat(start_iso)  # pl: "2025-09-05T19:30:00"
    m = Match(league_id=league.id, home_team_id=t_home.id, away_team_id=t_away.id,
              start_time=start, status="scheduled")
    db.add(m); db.commit(); db.refresh(m)
    return m

def add_odds_snapshot_1x2(db: Session, match_id: int, bookmaker: str, oh: float, od: float, oa: float):
    bk = get_or_create_bookmaker(db, bookmaker)
    for sel, o in (("H", oh), ("D", od), ("A", oa)):
        snap = OddsSnapshot(match_id=match_id, bookmaker_id=bk.id,
                            market="1X2", selection=sel, odds=o)
        db.add(snap)
    db.commit()

def main():
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_m = sub.add_parser("add-match", help="Új scheduled meccs felvétele")
    ap_m.add_argument("--league", required=True)
    ap_m.add_argument("--home", required=True)
    ap_m.add_argument("--away", required=True)
    ap_m.add_argument("--start", required=True, help='ISO idő: pl. "2025-09-05T19:30:00"')

    ap_o = sub.add_parser("add-odds", help="1X2 odds snapshot felvétele")
    ap_o.add_argument("--match-id", type=int, required=True)
    ap_o.add_argument("--bookmaker", required=True)
    ap_o.add_argument("--oh", type=float, required=True)
    ap_o.add_argument("--od", type=float, required=True)
    ap_o.add_argument("--oa", type=float, required=True)

    args = ap.parse_args()
    db = SessionLocal()

    if args.cmd == "add-match":
        m = add_match(db, args.league, args.home, args.away, args.start)
        print(f"✔ match created id={m.id}  {args.home} vs {args.away}  start={args.start}")

    elif args.cmd == "add-odds":
        add_odds_snapshot_1x2(db, args.match_id, args.bookmaker, args.oh, args.od, args.oa)
        print(f"✔ odds snapshot added for match_id={args.match_id} @ {args.bookmaker}")

    db.close()

if __name__ == "__main__":
    main()

