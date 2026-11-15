#!/usr/bin/env python
"""Verify fundamentals API returns data for ingested companies."""
import sys
from app.db.session import SessionLocal
from app.db.models import Company
from app.services.fundamentals_query import build_fundamentals_summary
from sqlalchemy import select

SYMBOLS = ["RELIANCE", "INFY", "TCS", "HDFCBANK"]

with SessionLocal() as db:
    for symbol in SYMBOLS:
        company = db.scalar(
            select(Company).where(Company.symbol == symbol, Company.is_active.is_(True))
        )
        
        if not company:
            print(f"[FAIL] {symbol}: Not found in database")
            continue
        
        try:
            summary = build_fundamentals_summary(db, company)
            
            # Check key fields are populated
            has_company_info = bool(summary.get("company", {}).get("name"))
            has_highlights = bool(summary.get("highlights"))
            has_ratios = bool(summary.get("ratios"))
            has_score = summary.get("score") is not None
            has_analysis = summary.get("analysis") is not None
            
            print(f"\n[OK] {symbol}: API returns data")
            print(f"  - Company info: {has_company_info}")
            print(f"  - Highlights (key metrics): {has_highlights}")
            print(f"  - Ratios: {has_ratios}")
            print(f"  - Fundamental score: {has_score}")
            print(f"  - Analysis: {has_analysis}")
            
            if has_company_info:
                print(f"  - Name: {summary['company']['name']}")
                print(f"  - Sector: {summary['company']['sector']}")
                print(f"  - Market Cap: {summary['company']['market_cap']}")
            
            if has_highlights:
                print(f"  - Highlights count: {len(summary['highlights'])}")
                for h in summary['highlights'][:3]:
                    print(f"    * {h.get('label')}: {h.get('value')}")
            
        except Exception as e:
            print(f"[FAIL] {symbol}: Error building summary: {type(e).__name__}: {str(e)[:100]}")
            import traceback
            traceback.print_exc()

print("\nDone!")

