from sqlalchemy.orm import Session
from datetime import datetime
from .db import SessionLocal
from .etl.store import upsert_fixture, insert_odds_snapshot
from .providers.localjson import load_from_file

def ingest_localjson(path: str):
    fixtures, quotes = load_from_file(path)
    db: Session = SessionLocal()
    try:
        # 1) fixture-k upsert
        id_map = {}  # ext_match_id -> match_id
        for fx in fixtures:
            m = upsert_fixture(db, fx)
            id_map[fx.ext_match_id] = m.id
        # 2) odds snapshotok
        for q in quotes:
            if q.ext_match_id in id_map:
                insert_odds_snapshot(db, q, id_map[q.ext_match_id])
        db.commit()
        print(f"✔ ingested fixtures={len(fixtures)}, odds={len(quotes)}")
    finally:
        db.close()

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="JSON feed path (local)")
    args = ap.parse_args()
    ingest_localjson(args.file)

if __name__ == "__main__":
    main()

