import os
from dotenv import load_dotenv

# .env a repo gyökerében
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hercules:hercules@localhost:5432/herculesbet",
)

# tippszűrés és tétezés
MIN_EDGE = float(os.getenv("MIN_EDGE", "0.02"))        # pl. 0.02 = 2%
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
IMPROVE_THRESHOLD = float(os.getenv("IMPROVE_THRESHOLD", "0.005"))
RHO = float(os.getenv("RHO", "0.05"))

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_SPORT_KEY = os.getenv("ODDS_SPORT_KEY", "soccer_epl")
ODDS_REGIONS = os.getenv("ODDS_REGIONS", "eu")
ODDS_MARKET = os.getenv("ODDS_MARKET", "h2h")

