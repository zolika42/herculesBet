import requests
from datetime import datetime, timezone
from typing import Tuple, List, Dict
from .base import Fixture, OddsQuote
from ..config import ODDS_API_KEY, ODDS_SPORT_KEY, ODDS_REGIONS, ODDS_MARKET

BASE_URL = "https://api.the-odds-api.com/v4"

def _iso_utc(s: str) -> datetime:
    # API ISO8601 → datetime (UTC)
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)

def fetch_fixtures_and_odds() -> Tuple[List[Fixture], List[OddsQuote]]:
    if not ODDS_API_KEY:
        raise RuntimeError("ODDS_API_KEY missing in env")

    # 1) upcoming events + odds egyben (v4/sports/{sport_key}/odds)
    url = f"{BASE_URL}/sports/{ODDS_SPORT_KEY}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": ODDS_REGIONS,
        "markets": ODDS_MARKET,
        "oddsFormat": "decimal"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    fixtures: List[Fixture] = []
    quotes: List[OddsQuote] = []

    for ev in data:
        ext_id = str(ev["id"])
        league = ev.get("sport_title") or ev.get("sport_key", "soccer")
        home = ev["home_team"]
        # az API esemény szinten ad csapatneveket (home/away).
        # away:
        # a ‘bookmakers’ sectionben a markets/outcomes jelöli a résztvevőket; az esemény szinten kell kinyerni az away-t:
        away = [t for t in ev.get("teams", []) if t != home]
        away = away[0] if away else "Away"

        start = _iso_utc(ev["commence_time"])
        fixtures.append(Fixture(ext_match_id=ext_id, league=league, home=home, away=away, start_time=start))

        # odds
        for bk in ev.get("bookmakers", []):
            bname = bk["title"]
            captured = _iso_utc(bk["last_update"])
            for market in bk.get("markets", []):
                if market.get("key") != ODDS_MARKET:
                    continue
                for outc in market.get("outcomes", []):
                    # h2h-nél name == team név; "Draw" is lehet
                    sel_name = outc.get("name")
                    price = float(outc.get("price"))
                    # map 1X2-re
                    if sel_name == home:
                        selection = "H"
                    elif sel_name == away:
                        selection = "A"
                    elif sel_name and sel_name.lower() == "draw":
                        selection = "D"
                    else:
                        continue
                    quotes.append(OddsQuote(
                        ext_match_id=ext_id,
                        bookmaker=bname,
                        market="1X2",
                        selection=selection,
                        odds=price,
                        captured_at=captured
                    ))
    return fixtures, quotes

