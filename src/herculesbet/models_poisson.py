from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from math import exp
import numpy as np
import math

from .models import Match, Team, League, ModelRun, Probability
from .config import RHO

# Hyperparaméterek (MVP)
MAX_GOALS = 10         # konvolúciós rács 0..MAX_GOALS
HFA_MULT = 1.10        # hazai gólvárható „szorzó”
REG = 1e-3             # kicsi regularizáció, hogy ne szálljanak el a szorzók
ITERS = 15             # tám/ved skálázás iterációk száma

@dataclass
class Rates:
    att: Dict[int, float] = field(default_factory=dict)  # team_id -> attack strength
    deff: Dict[int, float] = field(default_factory=dict) # team_id -> defence weakness (>=0)
    base_home: float = 1.3
    base_away: float = 1.1

def _collect_finished(db: Session, league_id: int):
    q = (
        db.query(Match)
        .filter(Match.league_id == league_id, Match.status == "finished")
        .all()
    )
    return q

def _init_rates(team_ids):
    r = Rates()
    for tid in team_ids:
        r.att[tid] = 1.0
        r.deff[tid] = 1.0
    return r

def fit_attack_defence(db: Session, league_id: int) -> Rates:
    """Egyszerű iteratív skálázás: goals ~ Pois( base * att_home * def_away )."""
    matches = _collect_finished(db, league_id)
    if not matches:
        # fallback paraméterek
        return Rates()

    # csapat lista
    team_ids = set()
    for m in matches:
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)
    rates = _init_rates(team_ids)

    # baseline gólátlagok liga-szinten
    hg = [m.home_score for m in matches if m.home_score is not None]
    ag = [m.away_score for m in matches if m.away_score is not None]
    rates.base_home = max(np.mean(hg), 0.6)
    rates.base_away = max(np.mean(ag), 0.6)

    # iteratív skálázás
    for _ in range(ITERS):
        # update attack
        num = {tid: REG for tid in team_ids}
        den = {tid: REG for tid in team_ids}
        for m in matches:
            lam_h = rates.base_home * rates.att[m.home_team_id] * rates.deff[m.away_team_id] * HFA_MULT
            lam_a = rates.base_away * rates.att[m.away_team_id] * rates.deff[m.home_team_id]
            # hozzájárulás
            num[m.home_team_id] += m.home_score if m.home_score is not None else 0.0
            den[m.home_team_id] += max(lam_h, 1e-6)
            num[m.away_team_id] += m.away_score if m.away_score is not None else 0.0
            den[m.away_team_id] += max(lam_a, 1e-6)
        for tid in team_ids:
            rates.att[tid] *= num[tid] / den[tid]

        # update defence (gyengébb = nagyobb szám; ezért goals against-hoz skálázunk)
        num = {tid: REG for tid in team_ids}
        den = {tid: REG for tid in team_ids}
        for m in matches:
            lam_h = rates.base_home * rates.att[m.home_team_id] * rates.deff[m.away_team_id] * HFA_MULT
            lam_a = rates.base_away * rates.att[m.away_team_id] * rates.deff[m.home_team_id]
            num[m.away_team_id] += m.home_score if m.home_score is not None else 0.0
            den[m.away_team_id] += max(rates.base_home * rates.att[m.home_team_id] * HFA_MULT, 1e-6)
            num[m.home_team_id] += m.away_score if m.away_score is not None else 0.0
            den[m.home_team_id] += max(rates.base_away * rates.att[m.away_team_id], 1e-6)
        for tid in team_ids:
            rates.deff[tid] *= num[tid] / den[tid]

    return rates

def poisson_prob_grid(lam_h: float, lam_a: float, max_goals=MAX_GOALS):
    i = np.arange(0, max_goals + 1)
    # P(X=i) = e^-λ λ^i / i!
    factorials = np.array([math.factorial(k) for k in i], dtype=float)
    ph = np.exp(-lam_h) * np.power(lam_h, i) / factorials
    pa = np.exp(-lam_a) * np.power(lam_a, i) / factorials
    mat = np.outer(ph, pa)  # P(H=i, A=j)
    return mat / mat.sum()  # normalizáció a levágás miatt

def probs_1x2_from_lambdas(lam_h: float, lam_a: float):
    mat = poisson_prob_grid(lam_h, lam_a, MAX_GOALS)
    # DC-korrekció
    if RHO != 0.0:
        mat = dixon_coles_adjust(mat, lam_h, lam_a, RHO)

    # 1X2 összegezés
    pH = np.tril(mat, -1).sum()
    pD = np.trace(mat)
    pA = np.triu(mat, 1).sum()
    s = pH + pD + pA
    return float(pH/s), float(pD/s), float(pA/s)

def run_poisson(db: Session) -> Tuple[int, int]:
    """Liga-szintű att/def becslés, majd scheduled meccsekre 1X2 valószínűségek."""
    leagues = db.query(League).all()
    mr = ModelRun(model_name="poisson_v0_1", version="0.1")
    db.add(mr); db.commit(); db.refresh(mr)

    total = 0
    for lg in leagues:
        rates = fit_attack_defence(db, lg.id)
        q = (
            db.query(Match)
            .filter(Match.league_id == lg.id, Match.status == "scheduled")
            .order_by(Match.start_time.asc())
        )
        for m in q.all():
            att_h = rates.att.get(m.home_team_id, 1.0)
            att_a = rates.att.get(m.away_team_id, 1.0)
            def_h = rates.deff.get(m.home_team_id, 1.0)
            def_a = rates.deff.get(m.away_team_id, 1.0)

            lam_h = max(rates.base_home * att_h * def_a * HFA_MULT, 0.05)
            lam_a = max(rates.base_away * att_a * def_h, 0.05)
            pH, pD, pA = probs_1x2_from_lambdas(lam_h, lam_a)
            for sel, p in (("H", pH), ("D", pD), ("A", pA)):
                db.add(Probability(
                    model_run_id=mr.id, match_id=m.id, market="1X2",
                    selection=sel, prob=p, fair_odds=round(1.0/max(p,1e-9), 4)
                ))
            total += 1
    db.commit()
    return mr.id, total

def dixon_coles_adjust(mat: np.ndarray, lam_h: float, lam_a: float, rho: float) -> np.ndarray:
    """
    DC-korrekció: a 0–0, 1–0, 0–1, 1–1 cellákat súlyozza.
    tau(0,0)=1 - rho*lam_h*lam_a
    tau(1,0)=1 + rho*lam_h
    tau(0,1)=1 + rho*lam_a
    tau(1,1)=1 - rho
    máshol: 1
    """
    mat = mat.copy()
    # biztonsági korlát: nehogy negatívba menjen
    def _clip(x): return max(x, 0.0000001)

    # 0-0
    mat[0,0] *= _clip(1.0 - rho * lam_h * lam_a)
    # 1-0
    if mat.shape[0] > 1:
        mat[1,0] *= _clip(1.0 + rho * lam_h)
    # 0-1
    if mat.shape[1] > 1:
        mat[0,1] *= _clip(1.0 + rho * lam_a)
    # 1-1
    if mat.shape[0] > 1 and mat.shape[1] > 1:
        mat[1,1] *= _clip(1.0 - rho)

    # renormalizálás, hogy összeg=1
    s = mat.sum()
    if s > 0:
        mat /= s
    return mat

