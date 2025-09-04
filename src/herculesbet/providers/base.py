from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

Selection = Literal["H", "D", "A"]

@dataclass
class Fixture:
    ext_match_id: str          # külső ID
    league: str
    home: str
    away: str
    start_time: datetime

@dataclass
class OddsQuote:
    ext_match_id: str
    bookmaker: str
    market: Literal["1X2"]
    selection: Selection       # "H" | "D" | "A"
    odds: float
    captured_at: datetime

