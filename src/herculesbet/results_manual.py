from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Match

def set_result(match_id: int, home_score: int, away_score: int):
    db: Session = SessionLocal()
    try:
        m = db.get(Match, match_id)
        if not m:
            raise SystemExit(f"Match {match_id} not found")
        m.home_score = home_score
        m.away_score = away_score
        m.status = "finished"
        db.commit()
        print(f"✔ set result match_id={match_id}: {home_score}-{away_score}")
    finally:
        db.close()

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--match-id", type=int, required=True)
    ap.add_argument("--home", type=int, required=True)
    ap.add_argument("--away", type=int, required=True)
    args = ap.parse_args()
    set_result(args.match_id, args.home, args.away)

if __name__ == "__main__":
    main()

