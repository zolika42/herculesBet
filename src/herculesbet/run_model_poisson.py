from .db import SessionLocal
from .models_poisson import run_poisson

def main():
    db = SessionLocal()
    run_id, n = run_poisson(db)
    db.close()
    print(f"✔ Poisson model probabilities stored for {n} matches (model_run_id={run_id})")

if __name__ == "__main__":
    main()

