from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSeed:
    name: str
    symbol: str
    provider_symbol: str
    exchange: str
    instrument_type: str
    sector: str | None = None


INSTRUMENTS = [
    InstrumentSeed("Reliance Industries", "RELIANCE", "RELIANCE.NS", "NSE", "company"),
    InstrumentSeed("Tata Consultancy Services", "TCS", "TCS.NS", "NSE", "company"),
    InstrumentSeed("HDFC Bank", "HDFCBANK", "HDFCBANK.NS", "NSE", "company"),
    InstrumentSeed("ICICI Bank", "ICICIBANK", "ICICIBANK.NS", "NSE", "company"),
    InstrumentSeed("Infosys", "INFY", "INFY.NS", "NSE", "company"),
    InstrumentSeed("ITC", "ITC", "ITC.NS", "NSE", "company"),
    InstrumentSeed("Larsen & Toubro", "LT", "LT.NS", "NSE", "company"),
    InstrumentSeed("State Bank of India", "SBIN", "SBIN.NS", "NSE", "company"),
    InstrumentSeed("Bharti Airtel", "BHARTIARTL", "BHARTIARTL.NS", "NSE", "company"),
    InstrumentSeed("Axis Bank", "AXISBANK", "AXISBANK.NS", "NSE", "company"),
    InstrumentSeed("Kotak Mahindra Bank", "KOTAKBANK", "KOTAKBANK.NS", "NSE", "company"),
    InstrumentSeed("Maruti Suzuki", "MARUTI", "MARUTI.NS", "NSE", "company"),
    InstrumentSeed("Sun Pharmaceutical", "SUNPHARMA", "SUNPHARMA.NS", "NSE", "company"),
    InstrumentSeed("Tata Motors", "TATAMOTORS", "TATAMOTORS.NS", "NSE", "company"),
    InstrumentSeed("Tata Steel", "TATASTEEL", "TATASTEEL.NS", "NSE", "company"),
    InstrumentSeed("Wipro", "WIPRO", "WIPRO.NS", "NSE", "company"),
    InstrumentSeed("Hindustan Unilever", "HINDUNILVR", "HINDUNILVR.NS", "NSE", "company"),
    InstrumentSeed("Bajaj Finance", "BAJFINANCE", "BAJFINANCE.NS", "NSE", "company"),
    InstrumentSeed("NTPC", "NTPC", "NTPC.NS", "NSE", "company"),
    InstrumentSeed("Power Grid Corporation", "POWERGRID", "POWERGRID.NS", "NSE", "company"),
    InstrumentSeed("NIFTY 50", "NIFTY50", "^NSEI", "NSE", "benchmark"),
    InstrumentSeed("SENSEX", "SENSEX", "^BSESN", "BSE", "benchmark"),
]
