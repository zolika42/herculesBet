from .db import SessionLocal
from .models_elo import run_elo

def main():
    db = SessionLocal()
    run_id, n = run_elo(db)
    db.close()
    print(f"✔ ELO model probabilities stored for {n} matches (model_run_id={run_id})")

if __name__ == "__main__":
    main()

