Project Name:
AI Investment Decision Engine

Market:
Indian equities

Universe:
NSE-listed stocks

Mode:
Research + Paper Trading

Prediction horizon:
30 trading days

Primary target:
Probability of achieving +5%
before hitting -3%

| Component     | V1 Decision                                 |
| ------------- | ------------------------------------------- |
| Market        | NSE                                         |
| Universe      | NIFTY 500                                   |
| Asset         | Equities                                    |
| Style         | Trend-following + momentum                  |
| Horizon       | 5–60 trading days                           |
| ML horizon    | 30 trading days                             |
| ML target     | +5% before −3%                              |
| Market filter | NIFTY regime                                |
| Sector filter | Relative strength                           |
| Technical     | SMA, SuperTrend, MACD, RSI, ATR, volume     |
| Fundamentals  | Growth, ROE, ROCE, debt, margins, FCF       |
| Valuation     | P/E, P/B, PEG, historical/sector comparison |
| ML            | Start Logistic → Random Forest → XGBoost    |
| Stop          | ATR + technical structure                   |
| Risk/trade    | 1%                                          |
| Max stock     | 10%                                         |
| Max sector    | 25%                                         |
| Max positions | 10                                          |
| Trading       | Paper trading initially                     |
| Execution     | No real-money automation in V1              |
| Backtest      | Walk-forward                                |
| Benchmark     | NIFTY 50 / NIFTY 500                        |

**Strategy A — Technical only**
SMA
SuperTrend
MACD
RSI
Volume

**Strategy B — Technical + Fundamental**
A + fundamentals

**Strategy C — Technical + Fundamental + Market/Sector**
B + market regime + sector strength

**Strategy D — Full ML**
C + ML