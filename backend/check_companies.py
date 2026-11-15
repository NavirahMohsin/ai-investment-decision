#!/usr/bin/env python
"""Quick check of what companies are in the database."""
from app.db.session import SessionLocal
from app.db.models import Company, CompanyFundamentalInfo
from sqlalchemy import select

with SessionLocal() as db:
    # Check active companies
    companies = list(db.scalars(
        select(Company).where(Company.is_active.is_(True)).limit(15)
    ))
    print(f"Total active companies: {len(companies)}\n")
    
    for c in companies:
        # Check if fundamentals exist
        has_info = db.scalar(
            select(CompanyFundamentalInfo.id)
            .where(CompanyFundamentalInfo.company_id == c.id)
            .limit(1)
        ) is not None
        
        status = "✓ Has fundamentals" if has_info else "✗ No fundamentals"
        print(f"{c.symbol:<12} {c.name:<30} {status}")
        print(f"             provider_symbol={c.provider_symbol}")
