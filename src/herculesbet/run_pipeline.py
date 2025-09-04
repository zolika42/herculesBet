import subprocess, sys, os

def run(cmd):
    print(f"\n$ {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        sys.exit(res.returncode)

def main():
    # 1) provider ingest – The Odds API
    try:
        run("python -m herculesbet.ingest_theodds")
    except SystemExit as e:
        raise
    except Exception as e:
        print(f"(warn) ingest failed: {e}")

    # 2) modell (Poisson/DC vagy ELO – amit szeretnél)
    run("python -m herculesbet.run_model_poisson")

    # 3) pick generálás
    run("python -m herculesbet.generate_picks")

    print("\n✔ pipeline done.")

if __name__ == "__main__":
    main()

