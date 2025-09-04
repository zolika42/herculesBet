# HerculesBet – Sports Betting Value Engine

## Overview
HerculesBet is an **end-to-end betting analysis system**:
- Pulls live odds and fixtures from providers (currently [The Odds API](https://the-odds-api.com)).
- Stores them in a PostgreSQL database with historical snapshots (for CLV analysis).
- Runs probability models (ELO, Poisson + Dixon–Coles correction).
- Generates **value picks** using edge detection + Kelly staking.
- Exposes everything through a clean **FastAPI HTTP API**.

---

## Quickstart on macOS

### 1. Install prerequisites
Make sure you have:
- **Homebrew** installed → [https://brew.sh](https://brew.sh)
- **Python 3.11+** → install with:
  ```bash
  brew install python@3.11
  ```
- **PostgreSQL** → easiest with Docker:
  ```bash
  brew install --cask docker
  open -a Docker
  ```
  Then in project root:
  ```bash
  docker-compose up -d
  ```

### 2. Clone project & create virtual environment
```bash
git clone https://github.com/zolika42/herculesBet.git
cd herculesBet
python3 -m venv .venv
source .venv/bin/activate
```

If you use **zsh** (default on modern macOS), you can put this in your `~/.zshrc` for convenience:
```bash
alias venv="source .venv/bin/activate"
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment
Copy example env:
```bash
cp .env.example .env
```

Edit `.env` and set:
```
DATABASE_URL=postgresql+psycopg://figyelo:figyelo@localhost:5432/figyelo
ODDS_API_KEY=your_api_key_here
ODDS_SPORT_KEY=soccer_epl
ODDS_REGIONS=eu
ODDS_MARKET=h2h
MIN_EDGE=0.02
KELLY_FRACTION=0.25
RHO=0.05
```

### 5. Run first ingestion + model + picks
```bash
export PYTHONPATH=src
python -m herculesbet.ingest_theodds
python -m herculesbet.run_model_poisson
python -m herculesbet.generate_picks
```

### 6. Start the API
```bash
uvicorn herculesbet.api:app --reload
```

Open in browser:
- Picks: [http://127.0.0.1:8000/picks](http://127.0.0.1:8000/picks)
- Stats: [http://127.0.0.1:8000/stats/summary](http://127.0.0.1:8000/stats/summary)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---


## Features
- 🔄 **Automated data ingestion**: fixtures + odds snapshots.
- 📊 **Probability models**: 
  - ELO (simple, result-based),
  - Poisson (goal-based, with Dixon–Coles correction).
- 💰 **Value betting**: edge calculated vs bookmaker odds.
- 🧮 **Kelly staking**: fractional staking suggestion.
- 📈 **CLV (Closing Line Value)** tracking.
- 🌐 **REST API**: picks, stats, health.

---

## Project Structure
```
src/herculesbet/
  ├── api.py             # FastAPI app
  ├── config.py          # Env config
  ├── db.py              # DB session/engine
  ├── models.py          # Core ORM models
  ├── models_poisson.py  # Poisson + Dixon–Coles
  ├── models_elo.py      # ELO model
  ├── generate_picks.py  # Pick generation logic
  ├── ingest_manual.py   # CLI for manual fixture/odds entry
  ├── ingest_provider.py # CLI for JSON provider ingest
  ├── ingest_theodds.py  # CLI for The Odds API ingest
  ├── etl/store.py       # Storage helpers (upsert, insert odds)
  └── providers/         # Provider adapters (localjson, theoddsapi, ...)
```

---

## Quickstart (Local)

### 1. Clone & Setup
```bash
git clone https://github.com/zolika42/herculesBet.git
cd herculesBet
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql+psycopg://figyelo:figyelo@localhost:5432/figyelo
ODDS_API_KEY=your_api_key_here
ODDS_SPORT_KEY=soccer_epl   # or soccer_hun_nbi if supported
ODDS_REGIONS=eu
ODDS_MARKET=h2h
MIN_EDGE=0.02
KELLY_FRACTION=0.25
RHO=0.05
```

Start Postgres with `docker-compose up -d`.

### 2. Ingest Data
Pull live odds + fixtures:
```bash
export PYTHONPATH=src
python -m herculesbet.ingest_theodds
```

### 3. Run Models
```bash
python -m herculesbet.run_model_poisson
```

### 4. Generate Picks
```bash
python -m herculesbet.generate_picks
```

### 5. Start API
```bash
uvicorn herculesbet.api:app --reload
```

Now visit:
- **http://127.0.0.1:8000/picks** → value bets (tips)
- **http://127.0.0.1:8000/stats/summary** → bankroll/ROI summary
- **http://127.0.0.1:8000/health** → health check

---

## Database
Main tables:
- `matches`: fixtures (home, away, league, start_time).
- `odds_snapshots`: odds history (used for CLV).
- `probabilities`: model-run probabilities.
- `edge_picks`: generated value picks.
- `leagues`, `teams`, `bookmakers`: reference tables.

---

## What To Do With The Data?
- **edge_picks** → the core: this is what you SELL to customers.
- **odds_snapshots** → historical odds, track **Closing Line Value (CLV)**.
- **probabilities** → raw model outputs, can debug/improve model.
- **matches** → full schedule with results (settled after finish).

---

## Example Workflow
```bash
# 1) Ingest live odds
python -m herculesbet.ingest_theodds

# 2) Run model (Poisson/DC)
python -m herculesbet.run_model_poisson

# 3) Generate picks
python -m herculesbet.generate_picks

# 4) Query picks
curl http://127.0.0.1:8000/picks
```

Output:
```json
[
  {
    "match_id": 42,
    "league": "EPL",
    "home": "Liverpool",
    "away": "Chelsea",
    "start_time": "2025-09-10T19:30:00",
    "selection": "H",
    "bookmaker": "BukiA",
    "odds": 2.10,
    "p_model": 0.55,
    "edge": 0.155,
    "stake_fraction": 0.023,
    "created_at": "2025-09-03T12:10:00",
    "status": "proposed"
  }
]
```

---

## Business Usage
- Run pipeline regularly → system ingests odds, generates picks.
- API `/picks` is your **tip feed**.
- Package these tips into a **monthly subscription** product.

---

## Notes
- Timezone: all UTC.
- Profit & stake are measured in **bankroll units**.
- Kelly fraction defaults to 0.25 for risk control.
- Models can be extended (O/U, AH).

