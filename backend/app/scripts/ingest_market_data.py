import argparse
from datetime import date, timedelta

from sqlalchemy import select

from app.core.config import DEFAULT_HISTORY_YEARS
from app.db.models import Company
from app.db.session import SessionLocal
from app.services.ingestion import ingest_instrument
from app.services.providers import YahooFinanceProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Download daily Yahoo Finance history into the local database.")
    parser.add_argument("--symbol", help="Internal symbol, for example RELIANCE or NIFTY50.")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--resolve", action="store_true", help="Resolve bare symbols to Yahoo suffixes (.NS, .BO)")
    args = parser.parse_args()
    start = args.start or (args.end - timedelta(days=365 * DEFAULT_HISTORY_YEARS))
    with SessionLocal() as db:
        query = select(Company).where(Company.is_active.is_(True))
        if args.symbol:
            query = query.where(Company.symbol == args.symbol.upper())
        companies = list(db.scalars(query))
        if args.symbol and not companies:
            raise SystemExit(f"Unknown instrument: {args.symbol}")
        
        provider = YahooFinanceProvider()
        unresolved = []
        
        for company in companies:
            provider_symbol = company.provider_symbol
            
            # Optionally resolve symbol with fallbacks
            if args.resolve:
                resolved, status, tried = provider.resolve_symbol(company.symbol)
                if resolved:
                    provider_symbol = resolved
                    print(f"{company.symbol}: Resolved to {provider_symbol}")
                else:
                    unresolved.append((company.symbol, status, tried))
                    print(f"{company.symbol}: Failed to resolve ({status}); tried: {', '.join(tried)}")
                    continue
            
            run = ingest_instrument(db, company, provider, start, args.end)
            status_msg = "✓ OK" if run.status == "success" else f"✗ {run.status}"
            print(f"  {status_msg}: downloaded={run.records_downloaded} inserted={run.records_inserted} updated={run.records_updated}")
            if run.error_message:
                print(f"  Error: {run.error_message}")
        
        if unresolved:
            print(f"\n{len(unresolved)} symbols could not be resolved:")
            for symbol, status, tried in unresolved:
                print(f"  {symbol}: {status} (tried: {', '.join(tried)})")


if __name__ == "__main__":
    main()
