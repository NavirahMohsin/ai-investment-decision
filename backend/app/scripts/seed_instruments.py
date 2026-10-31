from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Company
from app.services.universe import INSTRUMENTS


def seed() -> int:
    with SessionLocal() as db:
        inserted = 0
        for instrument in INSTRUMENTS:
            existing = db.scalar(select(Company).where(Company.symbol == instrument.symbol))
            if existing is None:
                db.add(Company(**instrument.__dict__))
                inserted += 1
        db.commit()
    return inserted


if __name__ == "__main__":
    print(f"Seeded {seed()} new instruments.")
