"""Manual script to ingest fundamental data for companies."""
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from app.db.models import Company
from app.db.session import SessionLocal
from app.services.fundamentals import (
    ingest_all_companies_fundamentals,
    ingest_company_fundamentals,
)
from app.services.providers.yahoo import YahooFinanceProvider


def main():
    parser = argparse.ArgumentParser(
        description="Ingest fundamental data for companies"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Specific company symbol to ingest (default: all active companies)",
    )
    parser.add_argument(
        "--skip-info",
        action="store_true",
        help="Skip company information ingestion",
    )
    parser.add_argument(
        "--skip-statements",
        action="store_true",
        help="Skip financial statements ingestion",
    )
    parser.add_argument(
        "--skip-ratios",
        action="store_true",
        help="Skip financial ratios ingestion",
    )
    
    args = parser.parse_args()
    
    with SessionLocal() as db:
        if args.symbol:
            # Ingest specific company
            company = db.scalar(
                select(Company).where(
                    Company.symbol == args.symbol.upper(),
                    Company.is_active.is_(True),
                )
            )
            
            if not company:
                print(f"Error: Company {args.symbol} not found or not active")
                return 1
            
            print(f"Ingesting fundamentals for {company.symbol} ({company.name})...")
            
            provider = YahooFinanceProvider()
            result = ingest_company_fundamentals(
                db,
                company,
                provider,
                include_info=not args.skip_info,
                include_statements=not args.skip_statements,
                include_ratios=not args.skip_ratios,
            )
            
            print(f"\nResult for {result['company_symbol']}:")
            print(f"  Success: {result['success']}")
            print(f"  Info updated: {result['company_info_updated']}")
            print(f"  Financials inserted: {result['financials_inserted']}")
            print(f"  Financials updated: {result['financials_updated']}")
            print(f"  Ratios inserted: {result['ratios_inserted']}")
            
            if result['error']:
                print(f"  Error: {result['error']}")
                return 1
        
        else:
            # Ingest all companies
            print("Ingesting fundamentals for all active companies...")
            print(f"Include info: {not args.skip_info}")
            print(f"Include statements: {not args.skip_statements}")
            print(f"Include ratios: {not args.skip_ratios}")
            print()
            
            run = ingest_all_companies_fundamentals(
                db,
                include_info=not args.skip_info,
                include_statements=not args.skip_statements,
                include_ratios=not args.skip_ratios,
            )
            
            print(f"\nIngestion completed:")
            print(f"  Status: {run.status}")
            print(f"  Companies processed: {run.companies_processed}")
            print(f"  Successful: {run.successful_count}")
            print(f"  Failed: {run.failed_count}")
            
            if run.failed_symbols:
                print(f"  Failed symbols: {run.failed_symbols}")
            
            duration = (run.completed_at - run.started_at).total_seconds() if run.completed_at else 0
            print(f"  Duration: {duration:.1f} seconds")
            
            if run.status == "failed":
                return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
