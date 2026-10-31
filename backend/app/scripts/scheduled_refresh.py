"""Scheduled market data refresh with smart timing."""
import argparse
import time
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.services.market_data import market_session, MarketSession
from app.services.refresh import refresh_live_quotes, refresh_market_data

IST = ZoneInfo("Asia/Kolkata")


def should_run_refresh(check_market_hours: bool = True) -> bool:
    """Determine if refresh should run based on market status."""
    if not check_market_hours:
        return True
    
    session = market_session()
    
    # Run during market hours and shortly after close
    if session in {MarketSession.PRE_OPEN, MarketSession.OPEN}:
        return True
    
    # Run once after market close
    now = datetime.now(IST)
    if session == MarketSession.CLOSED:
        # Check if it's within 30 minutes after market close (15:30)
        if dt_time(15, 30) <= now.time() <= dt_time(16, 0):
            return True
    
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scheduled market data refresh with market-aware timing"
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
        help="Refresh interval during market hours (default: 15 minutes)",
    )
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Also refresh historical OHLCV data (runs once daily)",
    )
    parser.add_argument(
        "--ignore-hours",
        action="store_true",
        help="Run regardless of market hours (for testing)",
    )
    parser.add_argument(
        "--store-snapshots",
        action="store_true",
        default=True,
        help="Store market snapshots in database",
    )
    
    args = parser.parse_args()
    
    if args.interval_minutes < 1:
        raise SystemExit("--interval-minutes must be at least 1")
    
    print(f"Starting scheduled market data refresh (interval: {args.interval_minutes} minutes)")
    print(f"Market hours check: {'disabled' if args.ignore_hours else 'enabled'}")
    print(f"Historical refresh: {'enabled' if args.historical else 'disabled'}")
    print(f"Snapshot storage: {'enabled' if args.store_snapshots else 'disabled'}")
    print()
    
    last_historical_refresh = None
    
    while True:
        try:
            current_time = datetime.now(IST)
            session_status = market_session()
            
            if should_run_refresh(not args.ignore_hours):
                print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S IST')}] Market: {session_status.value}")
                
                # Refresh live quotes
                with SessionLocal() as db:
                    print("  Refreshing live quotes...")
                    quote_result = refresh_live_quotes(db, args.store_snapshots)
                    print(f"  Quotes: {quote_result['successful']} successful, {quote_result['failed']} failed")
                    if quote_result['failed_symbols']:
                        print(f"  Failed symbols: {', '.join(quote_result['failed_symbols'])}")
                
                # Refresh historical data once per day
                if args.historical:
                    today = current_time.date()
                    if last_historical_refresh != today:
                        with SessionLocal() as db:
                            print("  Refreshing historical data...")
                            hist_result = refresh_market_data(db)
                            print(f"  Historical: {hist_result['instruments_processed']} instruments, "
                                  f"{hist_result['successful_runs']} successful, "
                                  f"{hist_result['failed_runs']} failed")
                            last_historical_refresh = today
                
                print()
            else:
                print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S IST')}] Market: {session_status.value} - Skipping refresh")
                print()
        
        except KeyboardInterrupt:
            print("\nShutting down scheduled refresh...")
            break
        except Exception as error:
            print(f"Error during refresh: {error}")
            print()
        
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()
