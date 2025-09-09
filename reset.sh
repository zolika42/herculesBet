#!/usr/bin/env bash
set -euo pipefail

# ---- Beállítások
DB_URL="postgresql://hercules:hercules@localhost:5432/herculesbet"
BACKUP="/var/www/html/db_backup_$(date +%F_%H%M%S).dump"

# ---- Szolgáltatások leállítása, hogy ne írjanak közben
sudo systemctl stop hercules-refresh.timer || true
sudo systemctl stop hercules-refresh.service || true
sudo systemctl stop herculesbet.service || true

# ---- Mentés (ha bármi kéne visszaút)
pg_dump -U hercules -h localhost -d herculesbet -Fc -f "$BACKUP" || true
echo "Backup: $BACKUP"

# ---- Adatbázis teljes takarítás (IDENTITY reset + CASCADE)
psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
TRUNCATE TABLE
  odds_snapshots,
  probabilities,
  picks,
  edge_picks,
  model_runs,
  matches,
  teams,
  leagues,
  bookmakers
RESTART IDENTITY CASCADE;
SQL

# ---- App környezet
cd /var/www/html
source .venv/bin/activate
export PYTHONPATH=/var/www/html/src
set -a; source .env; set +a

# ---- Séma/indextábla újra
python -m herculesbet.db_init

# (hasznos indexek — gyors lekérdezésekhez)
psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE INDEX IF NOT EXISTS ix_odds_snapshots_recent
  ON odds_snapshots (captured_at DESC);
CREATE INDEX IF NOT EXISTS ix_odds_snapshots_match_sel
  ON odds_snapshots (match_id, selection, captured_at DESC);
SQL

# ---- Ingesztálás + modell + pickek
python -m herculesbet.ingest_theodds
python -m herculesbet.run_model_poisson

# első körben engedjük bőven az edge-et és az összes közelgő meccset
MIN_EDGE=0.00 \
KELLY_FRACTION=0.25 \
UPCOMING_ONLY=true \
UPCOMING_GRACE_MIN=15 \
LOOKBACK_HOURS=48 \
python -m herculesbet.generate_picks

# ---- Gyors sanity checkek
echo "=== model_runs ==="
psql "$DB_URL" -c "TABLE model_runs;"

echo "=== picks számláló ==="
psql "$DB_URL" -c "SELECT COUNT(*) AS picks_cnt, to_char(MAX(created_at),'YYYY-MM-DD HH24:MI') AS last_pick FROM picks;"

echo "=== edge_picks számláló ==="
psql "$DB_URL" -c "SELECT COUNT(*) AS edge_cnt, to_char(MAX(created_at),'YYYY-MM-DD HH24:MI') AS last_edge FROM edge_picks;"

echo "=== top 10 edge_picks ==="
psql "$DB_URL" -c "
SELECT
  ep.match_id,
  l.name AS league,
  th.name AS home,
  ta.name AS away,
  ep.market,
  ep.selection,
  ROUND(ep.offered_odds::numeric, 2)  AS odds,
  ROUND(ep.model_prob::numeric, 3)    AS p_model,
  ROUND(ep.edge::numeric, 3)          AS edge,
  ROUND(ep.stake_fraction::numeric, 3) AS stake,
  to_char(ep.created_at,'YYYY-MM-DD HH24:MI') AS created_at
FROM edge_picks ep
JOIN matches m ON m.id = ep.match_id
JOIN leagues l ON l.id = m.league_id
JOIN teams th ON th.id = m.home_team_id
JOIN teams ta ON ta.id = m.away_team_id
ORDER BY ep.created_at DESC
LIMIT 10;
"

# ---- API újraindítás és ellenőrzés
sudo systemctl restart herculesbet.service
sleep 1
curl -s 'http://127.0.0.1:3000/health' || true
curl -s 'http://127.0.0.1:3000/picks?limit=20&min_edge=0&upcoming_only=false' || true

# ---- Időzítő vissza
sudo systemctl start hercules-refresh.service || true
sudo systemctl enable --now hercules-refresh.timer || true
systemctl list-timers --all | grep hercules-refresh || true

echo "=== KÉSZ ==="

