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
        start = _iso_utc(ev["commence_time"])
        fixtures.append(Fixture(ext_match_id=ext_id, league=league, home=home, away=away, start_time=start))
        # --- a ciklus elején, ev-ből olvasva:
        home = (ev.get("home_team") or "").strip()
        teams = [t.strip() for t in ev.get("teams", []) if isinstance(t, str)]
        # ha van explicit away_team, használd azt; különben teams-ből a nem-home elem
        away = (ev.get("away_team") or next((t for t in teams if t != home), "")).strip()
        home_cf = home.casefold()
        away_cf = away.casefold()

        # odds
        for bk in ev.get("bookmakers", []):
            bname = bk.get("title") or bk.get("key")
            captured = _iso_utc(bk["last_update"])
            for market in bk.get("markets", []):
                if market.get("key") != ODDS_MARKET:
                    continue
                for outc in market.get("outcomes", []):
                    oname = (outc.get("name") or "").strip()
                    if not oname:
                        continue
                    price = outc.get("price")
                    if price is None:
                        continue
                    ocf = oname.casefold()

                    # 1) Draw/Tie
                    if ocf in ("draw", "tie"):
                        sel = "D"
                    # 2) pontos egyezés
                    elif ocf == home_cf:
                        sel = "H"
                    elif ocf == away_cf:
                        sel = "A"
                    # 3) laza egyezés (aliasok, whitespace, rövidítések)
                    elif home_cf and home_cf in ocf:
                        sel = "H"
                    elif away_cf and away_cf in ocf:
                        sel = "A"
                    # 4) utolsó próbálkozás: ha az outcome egy a teams-ből, ami nem home → A
                    elif oname in teams and oname != home:
                        sel = "A"
                    else:
                        # ismeretlen kimenet: hagyjuk ki
                        continue

                    quotes.append(OddsQuote(
                        ext_match_id=str(ev["id"]),
                        bookmaker=bname,
                        market="1X2" if ODDS_MARKET == "h2h" else ODDS_MARKET,
                        selection=sel,
                        odds=float(price),
                        captured_at=captured
                    ))
    return fixtures, quotes

