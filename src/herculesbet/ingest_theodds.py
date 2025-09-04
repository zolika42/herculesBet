from sqlalchemy.orm import Session
from .db import SessionLocal
from .etl.store import upsert_fixture, insert_odds_snapshot
from .providers.theoddsapi import fetch_fixtures_and_odds

def main():
    fixtures, quotes = fetch_fixtures_and_odds()
    db: Session = SessionLocal()
    try:
        id_map = {}
        for fx in fixtures:
            m = upsert_fixture(db, fx)
            id_map[fx.ext_match_id] = m.id
        for q in quotes:
            mid = id_map.get(q.ext_match_id)
            if mid:
                insert_odds_snapshot(db, q, mid)
        db.commit()
        print(f"✔ the-odds-api ingested fixtures={len(fixtures)}, odds={len(quotes)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()

