from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Float, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class League(Base):
    __tablename__ = "leagues"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    sport = Column(String, nullable=False, default="football")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    name = Column(String, nullable=False)
    league = relationship("League")
    __table_args__ = (UniqueConstraint('league_id', 'name', name='uq_team_league_name'),)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="scheduled")  # scheduled|live|finished
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)

    league = relationship("League")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])

class Bookmaker(Base):
    __tablename__ = "bookmakers"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    market = Column(String, nullable=False)      # pl. '1X2'
    selection = Column(String, nullable=False)   # 'H'|'D'|'A'
    odds = Column(Float, nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint('match_id','bookmaker_id','market','selection','captured_at',
                         name='uq_odds_point_in_time'),
    )

class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(Integer, primary_key=True)
    model_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    run_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    params = Column(JSON, nullable=True)

class Probability(Base):
    __tablename__ = "probabilities"
    id = Column(Integer, primary_key=True)
    model_run_id = Column(Integer, ForeignKey("model_runs.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    market = Column(String, nullable=False)     # '1X2'
    selection = Column(String, nullable=False)  # 'H'|'D'|'A'
    prob = Column(Float, nullable=False)        # 0..1
    fair_odds = Column(Float, nullable=False)   # 1/prob (kalibrált)

    __table_args__ = (
        UniqueConstraint('model_run_id','match_id','market','selection',
                         name='uq_prob_unique'),
    )

class EdgePick(Base):
    __tablename__ = "edge_picks"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    market = Column(String, nullable=False)
    selection = Column(String, nullable=False)      # 'H'|'D'|'A'
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    offered_odds = Column(Float, nullable=False)
    model_prob = Column(Float, nullable=False)
    edge = Column(Float, nullable=False)            # (p_model - p_book)/p_book
    stake_fraction = Column(Float, nullable=False)  # bankroll részarány (0..1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String, nullable=False, default="proposed")  # proposed|placed|settled
    result = Column(String, nullable=True)          # win|loss|push
    profit = Column(Float, nullable=True)           # HUF
    closing_odds = Column(Float, nullable=True)
    clv = Column(Float, nullable=True)

class BankrollLog(Base):
    __tablename__ = "bankroll_log"
    id = Column(Integer, primary_key=True)
    at = Column(DateTime, default=datetime.utcnow, nullable=False)
    bankroll = Column(Float, nullable=False)

