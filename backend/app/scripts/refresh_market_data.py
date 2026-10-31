import argparse
import time

from app.db.session import SessionLocal
from app.services.refresh import refresh_market_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh stored Yahoo Finance market history.")
    parser.add_argument("--symbol", help="Internal symbol, for example RELIANCE or NIFTY50.")
    parser.add_argument("--interval-minutes", type=int, default=0, help="Repeat after this many minutes; 0 runs once.")
    args = parser.parse_args()
    if args.interval_minutes < 0:
        raise SystemExit("--interval-minutes cannot be negative")
    while True:
        with SessionLocal() as db:
            result = refresh_market_data(db, args.symbol)
            print(result, flush=True)
        if args.interval_minutes == 0:
            return
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()
