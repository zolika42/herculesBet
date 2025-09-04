from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from ..models import League, Team, Match, Bookmaker, OddsSnapshot
from ..providers.base import Fixture, OddsQuote
from sqlalchemy.dialects.postgresql import insert

def get_or_create_league(db: Session, name: str, country="") -> League:
    obj = db.execute(select(League).where(League.name == name)).scalar_one_or_none()
    if obj: return obj
    obj = League(name=name, country=country or None, sport="football")
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_or_create_team(db: Session, league_id: int, name: str) -> Team:
    obj = db.execute(select(Team).where(Team.league_id==league_id, Team.name==name)).scalar_one_or_none()
    if obj: return obj
    obj = Team(league_id=league_id, name=name)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_or_create_bookmaker(db: Session, name: str) -> Bookmaker:
    obj = db.execute(select(Bookmaker).where(Bookmaker.name==name)).scalar_one_or_none()
    if obj: return obj
    obj = Bookmaker(name=name)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def upsert_fixture(db: Session, fx: Fixture) -> Match:
    lg = get_or_create_league(db, fx.league)
    h = get_or_create_team(db, lg.id, fx.home)
    a = get_or_create_team(db, lg.id, fx.away)
    # keresünk azonos (liga, home, away, start) alapján
    q = select(Match).where(
        Match.league_id==lg.id,
        Match.home_team_id==h.id,
        Match.away_team_id==a.id,
        Match.start_time==fx.start_time
    )
    m = db.execute(q).scalar_one_or_none()
    if m: return m
    m = Match(league_id=lg.id, home_team_id=h.id, away_team_id=a.id,
              start_time=fx.start_time, status="scheduled")
    db.add(m); db.commit(); db.refresh(m); return m

def insert_odds_snapshot(db: Session, oq: OddsQuote, match_id: int):
    bk = get_or_create_bookmaker(db, oq.bookmaker)

    stmt = insert(OddsSnapshot).values(
        match_id=match_id,
        bookmaker_id=bk.id,
        market=oq.market,
        selection=oq.selection,
        odds=oq.odds,
        captured_at=oq.captured_at,
    )

    # Ha ugyanazzal a kulccsal már van rekord, frissítjük az odds értékét.
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            OddsSnapshot.match_id,
            OddsSnapshot.bookmaker_id,
            OddsSnapshot.market,
            OddsSnapshot.selection,
            OddsSnapshot.captured_at,
        ],
        set_={"odds": oq.odds},
    )
    db.execute(stmt)
