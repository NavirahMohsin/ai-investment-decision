#!/usr/bin/env python
"""Quick fundamentals ingest for Indian companies with improved provider."""
import time
from app.db.session import SessionLocal
from app.db.models import Company
from app.services.providers.yahoo import YahooFinanceProvider
from app.services.fundamentals import ingest_company_fundamentals
from sqlalchemy import select

SYMBOLS = ["RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK", "SBIN"]

with SessionLocal() as db:
    provider = YahooFinanceProvider(min_pause=1.0)  # 1 second pause
    
    for i, symbol in enumerate(SYMBOLS, 1):
        company = db.scalar(
            select(Company).where(Company.symbol == symbol, Company.is_active.is_(True))
        )
        
        if not company:
            print(f"[{i}/{len(SYMBOLS)}] {symbol}: Not found in database")
            continue
        
        print(f"[{i}/{len(SYMBOLS)}] {symbol}: Resolving symbol...")
        resolved, status, tried = provider.resolve_symbol(symbol)
        
        if not resolved:
            print(f"       ✗ Could not resolve: {status}")
            print(f"       Tried: {', '.join(tried)}")
            continue
        
        print(f"       ✓ Resolved to {resolved}")
        print(f"       Ingesting fundamentals...")
        
        try:
            result = ingest_company_fundamentals(
                db,
                company,
                provider,
                include_info=True,
                include_statements=True,
                include_ratios=True,
            )
            
            if result["success"]:
                print(f"       ✓ Success!")
                print(f"         - Company info: {'updated' if result['company_info_updated'] else 'skipped'}")
                print(f"         - Financials: {result['financials_inserted']} inserted, {result['financials_updated']} updated")
                print(f"         - Ratios: {result['ratios_inserted']} inserted")
            else:
                print(f"       ✗ Failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"       ✗ Error: {type(e).__name__}: {str(e)[:100]}")
        
        # Pause before next company
        if i < len(SYMBOLS):
            print(f"       Pausing 3s before next company...\n")
            time.sleep(3)

print("\nDone!")
