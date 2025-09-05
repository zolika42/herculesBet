import os
import sys
import subprocess
from datetime import datetime

def run(modname: str):
    print(f"[{datetime.utcnow().isoformat()}Z] -> python -m {modname}", flush=True)
    subprocess.run([sys.executable, "-m", modname], check=True)

def main():
    # Opcionális: csak akkor próbáljuk az API-Football ingestet, ha van kulcs
    api_football_key = os.getenv("API_FOOTBALL_KEY", "").strip()

    # 1) The Odds API ingest (biztosan működik nálad)
    run("herculesbet.ingest_theodds")

    # 2) API-Football ingest (ha van kulcsod és be van kötve)
    if api_football_key:
        try:
            run("herculesbet.ingest_apifootball")
        except Exception as e:
            print(f"[WARN] ingest_apifootball skipped with error: {e}", flush=True)

    # 3) Modellek
    run("herculesbet.run_model_poisson")

    # 4) Picks generálás
    run("herculesbet.generate_picks")

if __name__ == "__main__":
    try:
        main()
        print(f"[{datetime.utcnow().isoformat()}Z] DONE", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] step failed: {e}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] unexpected: {e}", flush=True)
        sys.exit(1)

