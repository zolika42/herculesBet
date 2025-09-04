from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import Match, Team, League, ModelRun, Probability

# --- Paraméterek ---
K_DEFAULT = 20.0       # ELO frissítés erőssége
HFA_PTS   = 60.0       # hazai pálya előny pontban (liga-függő lehet, MVP-re fix)
ELO_INIT  = 1500.0     # kezdő rating
FALLBACK_DRAW_RATE = 0.26  # ha nincs elég adat

def logistic_winprob(rdiff_pts: float) -> float:
    """P(home beats away) a döntetlen nélküli modellben."""
    return 1.0 / (1.0 + 10.0 ** ( - rdiff_pts / 400.0))

@dataclass
class EloState:
    ratings: Dict[int, float] = field(default_factory=dict)   # team_id -> elo
    draws: int = 0
    games: int = 0

    def rating(self, team_id: int) -> float:
        return self.ratings.get(team_id, ELO_INIT)

    def update(self, home_id: int, away_id: int, result: str, k: float = K_DEFAULT):
        """result: 'H' | 'D' | 'A'"""
        rh = self.rating(home_id)
        ra = self.rating(away_id)

        # hazai előny hozzáadása a valószínűségi térhez
        p_home_star = logistic_winprob((rh + HFA_PTS) - ra)
        p_away_star = 1.0 - p_home_star

        # "cél" eredmény (döntetlen nélkül)
        if result == "H":
            s_home = 1.0
        elif result == "A":
            s_home = 0.0
        else:  # 'D' -> középen frissítünk
            s_home = 0.5

        # ELO frissítés
        d_home = k * (s_home - p_home_star)
        rh2 = rh + d_home
        ra2 = ra - d_home

        self.ratings[home_id] = rh2
        self.ratings[away_id] = ra2

        # draw stat
        self.games += 1
        if result == "D":
            self.draws += 1

def learn_elo_for_league(db: Session, league_id: int) -> EloState:
    """Végigmegy a lezárt meccseken időrendben és tanulja az ELO-t."""
    st = EloState()
    q = (
        db.query(Match)
        .filter(Match.league_id == league_id, Match.status == "finished")
        .order_by(Match.start_time.asc())
    )
    for m in q.all():
        if m.home_score is None or m.away_score is None:
            continue
        if m.home_score > m.away_score:
            res = "H"
        elif m.home_score < m.away_score:
            res = "A"
        else:
            res = "D"
        st.update(m.home_team_id, m.away_team_id, res)
    return st

def league_draw_rate(state: EloState) -> float:
    if state.games >= 20:  # ha van elég adat, használjuk a ligából
        return state.draws / state.games
    return FALLBACK_DRAW_RATE

def schedule_probs_for_league(db: Session, league_id: int, state: EloState) -> Tuple[int, int]:
    """Kiírja a valószínűségeket a 'scheduled' meccsekre a ligában."""
    mr = ModelRun(model_name="elo_v0_1", version="0.1")
    db.add(mr); db.commit(); db.refresh(mr)

    pD = league_draw_rate(state)
    n_matches = 0
    q = (
        db.query(Match)
        .filter(Match.league_id == league_id, Match.status == "scheduled")
        .order_by(Match.start_time.asc())
    )
    for m in q.all():
        rh = state.rating(m.home_team_id)
        ra = state.rating(m.away_team_id)
        pH_star = logistic_winprob((rh + HFA_PTS) - ra)
        # elosztjuk a maradékot a két kimenetel között
        pH = (1.0 - pD) * pH_star
        pA = (1.0 - pD) * (1.0 - pH_star)
        # normalizáció végett (numerikai biztonság)
        s = pH + pD + pA
        pH, pD_n, pA = pH/s, pD/s, pA/s

        for sel, p in (("H", pH), ("D", pD_n), ("A", pA)):
            db.add(Probability(
                model_run_id=mr.id, match_id=m.id, market="1X2",
                selection=sel, prob=float(p), fair_odds=round(1.0/max(p,1e-9), 4)
            ))
        n_matches += 1

    db.commit()
    return mr.id, n_matches

def run_elo(db: Session) -> Tuple[int, int]:
    """Tanul minden ligára, majd kiírja a scheduled meccsekre a probabilityt."""
    leagues = db.query(League).all()
    total_matches = 0
    last_run_id = None
    for lg in leagues:
        st = learn_elo_for_league(db, lg.id)
        run_id, n = schedule_probs_for_league(db, lg.id, st)
        total_matches += n
        last_run_id = run_id
    return (last_run_id or 0), total_matches

