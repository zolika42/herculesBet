from .db import Base, engine
# model osztályok importja, hogy a táblák regisztrálva legyenek:
from .models import (
    League, Team, Match, Bookmaker, OddsSnapshot,
    ModelRun, Probability, EdgePick, BankrollLog
)

def main():
    Base.metadata.create_all(bind=engine)
    print("✔ Tables created in database.")

if __name__ == "__main__":
    main()

