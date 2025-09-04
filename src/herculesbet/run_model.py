from .db import SessionLocal
from .models_baseline import run

def main():
    db = SessionLocal()
    run_id, n = run(db)
    db.close()
    print(f"✔ probabilities stored for {n} matches (model_run_id={run_id})")

if __name__ == "__main__":
    main()

