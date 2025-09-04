import json
from datetime import datetime, timezone
from typing import Tuple, List
from .base import Fixture, OddsQuote

def load_from_file(path: str) -> Tuple[List[Fixture], List[OddsQuote]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fixtures, odds = [], []
    for fx in data.get("fixtures", []):
        fixtures.append(Fixture(
            ext_match_id=str(fx["ext_match_id"]),
            league=fx["league"],
            home=fx["home"],
            away=fx["away"],
            start_time=datetime.fromisoformat(fx["start_time"]),
        ))
    for q in data.get("odds", []):
        odds.append(OddsQuote(
            ext_match_id=str(q["ext_match_id"]),
            bookmaker=q["bookmaker"],
            market="1X2",
            selection=q["selection"],
            odds=float(q["odds"]),
            captured_at=datetime.fromisoformat(q["captured_at"]),
        ))
    return fixtures, odds

