"""
Egyszerű baseline: minden scheduled meccsre fix 1X2 valószínűségeket ír.
Később DC/Poisson/ELO váltja.
"""
from sqlalchemy.orm import Session
from .models import Match, ModelRun, Probability

P = {"H": 0.45, "D": 0.27, "A": 0.28}  # home-advantage íz

def run(db: Session, model_name="baseline", version="0.1"):
    mr = ModelRun(model_name=model_name, version=version)
    db.add(mr); db.commit(); db.refresh(mr)
    count = 0
    for m in db.query(Match).filter_by(status="scheduled").all():
        for sel, p in P.items():
            db.add(Probability(
                model_run_id=mr.id, match_id=m.id, market="1X2",
                selection=sel, prob=p, fair_odds=round(1.0 / max(p, 1e-9), 4)
            ))
        count += 1
    db.commit()
    return mr.id, count

