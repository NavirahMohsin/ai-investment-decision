#!/usr/bin/env python
"""
Test script to verify Yahoo Finance provider improvements with Indian symbols.

This demonstrates:
1. Symbol resolution (.NS / .BO fallback)
2. Rate limit detection and backoff
3. Log capture for hidden errors
4. Inter-request pause to prevent hammering
"""

import sys
import logging
from datetime import date, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, "/app")

from app.services.providers.yahoo import YahooFinanceProvider


def test_symbol_resolution():
    """Test symbol resolution with fallbacks."""
    print("\n" + "="*60)
    print("TEST 1: Symbol Resolution")
    print("="*60)
    
    provider = YahooFinanceProvider()
    test_symbols = [
        "RELIANCE",      # Should resolve to RELIANCE.NS or RELIANCE.BO
        "INFY",          # Should resolve to INFY.NS
        "HDFCBANK",      # Should resolve to HDFCBANK.NS
        "TCS",           # Should resolve to TCS.NS
        "INVALID_SYMBOL_XYZ",  # Should fail with NOT_FOUND
    ]
    
    for symbol in test_symbols:
        resolved, status, tried = provider.resolve_symbol(symbol)
        if resolved:
            print(f"✓ {symbol:<25} → {resolved:<15} ({status})")
        else:
            print(f"✗ {symbol:<25} Failed: {status}")
            print(f"  Tried: {', '.join(tried)}")


def test_download_with_pause():
    """Test download with inter-request pause."""
    print("\n" + "="*60)
    print("TEST 2: Download with Rate Limit Protection")
    print("="*60)
    
    provider = YahooFinanceProvider(min_pause=0.5)  # Reduced pause for testing
    
    symbols = ["RELIANCE", "INFY", "HDFCBANK"]
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    for i, symbol in enumerate(symbols, 1):
        resolved, status, _ = provider.resolve_symbol(symbol)
        if not resolved:
            print(f"[{i}/{len(symbols)}] {symbol}: Could not resolve")
            continue
        
        print(f"[{i}/{len(symbols)}] {symbol}: Downloading {start_date} to {end_date}")
        result = provider._download_with_retry(resolved, start_date, end_date)
        
        if result["status"] == "ok":
            print(f"  ✓ Downloaded {len(result['rows'])} records")
        else:
            print(f"  ✗ {result['status'].upper()}: {result['reason']}")


def test_quote_with_pause():
    """Test quote retrieval with pause."""
    print("\n" + "="*60)
    print("TEST 3: Quote Retrieval with Pause")
    print("="*60)
    
    provider = YahooFinanceProvider(min_pause=0.5)
    
    symbols = ["RELIANCE", "INFY", "HDFCBANK"]
    
    for i, symbol in enumerate(symbols, 1):
        resolved, status, _ = provider.resolve_symbol(symbol)
        if not resolved:
            print(f"[{i}/{len(symbols)}] {symbol}: Could not resolve")
            continue
        
        print(f"[{i}/{len(symbols)}] {symbol}: Getting quote...")
        try:
            quote = provider.quote(resolved)
            price = quote.get("price")
            print(f"  ✓ Price: ₹{price:,.2f}" if price else "  ✓ Quote retrieved (no price data)")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {str(e)[:80]}")


def test_company_info():
    """Test company info retrieval."""
    print("\n" + "="*60)
    print("TEST 4: Company Info Retrieval")
    print("="*60)
    
    provider = YahooFinanceProvider(min_pause=0.5)
    
    symbols = ["RELIANCE", "INFY"]
    
    for symbol in symbols:
        resolved, status, _ = provider.resolve_symbol(symbol)
        if not resolved:
            print(f"✗ {symbol}: Could not resolve")
            continue
        
        print(f"\n{symbol}:")
        try:
            info = provider.get_company_info(resolved)
            print(f"  Name: {info.get('name')}")
            print(f"  Sector: {info.get('sector')}")
            print(f"  Industry: {info.get('industry')}")
            if info.get('market_cap'):
                print(f"  Market Cap: ${info['market_cap']:,}")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {str(e)[:80]}")


if __name__ == "__main__":
    try:
        test_symbol_resolution()
        test_download_with_pause()
        test_quote_with_pause()
        test_company_info()
        
        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
