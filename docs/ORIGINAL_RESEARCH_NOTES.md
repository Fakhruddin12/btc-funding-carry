# BTC funding carry: cash-ledger P&L

The main result is in output/pdf/Funding_carry_PnL_report.pdf. Both tests begin with 10,000 USDT and finish with all positions closed. The later test is a separate account, not a continuation through January 2025.

| USDT unless stated | 2022-2024 development | Feb-Dec 2025 later test |
|---|---:|---:|
| Funding income | 1,356.32 | 223.62 |
| Basis P&L | -6.00 | -0.22 |
| Fees | -53.06 | -21.86 |
| Slippage | -14.15 | -5.83 |
| Net P&L | 1,283.11 | 195.70 |
| Final cash | 11,283.11 | 10,195.70 |

The unrounded ledger reproduces the earlier feasibility study within 0.000001 USDT. Primary results add a 0.001 BTC research lot and mark-to-market/cash accounting. Fee and slippage scenarios are unchanged. Perpetual entry averages and realized partial closes are tracked. All USDT cash is assigned to futures collateral during holding periods; monthly spot rebalances are funded from actual cash. No cash borrowing is needed in either tested path.

The prior monthly feasibility report remains in RESEARCH_NOTES.md and legacy result files; latest cash-ledger results take precedence. Annual reporting now uses calendar marked valuations, and terminal January 1 cash flows are allocated to the concluding December. This causes small annual differences from the original monthly episode table in addition to lot rounding. Total fractional P&L reconciliation passes.

Both samples underperform a 5% annual compounded cash-hurdle scenario. Positive P&L is a research result, not evidence of predictive alpha or a live-trading recommendation. No funding forecast or selective entry signal has been fitted. Hourly trade-price execution and settlement-mark proxies, assumed commissions/slippage and scenario margin rules remain limitations. Exchange failure, stablecoin depegging and operational/legging risks are excluded.

## Files

- results/pnl/development and results/pnl/validation_2025 contain daily P&L statements, hourly marked ledgers, trades, funding payments, annual tables and summary JSON.
- results/pnl/equity_drawdown.png contains the equity, cost-stress and drawdown figure.
- PNL_PROTOCOL.json records choices before the later data download. PNL_REPORTING_CHANGES.md documents report-only changes; pnl_frozen_before_validation.py retains the frozen engine.
- Raw source archives and SHA-256 manifests are included. The native funding timestamp is used for booking; a scheduled-hour mark open approximates the settlement mark.

## Reproduce

Requires Python, numpy, pandas, matplotlib and reportlab. Source data are cached in raw/. Run from this folder:

```sh
python study.py
python continuous.py
python pnl.py
python pnl.py --validation
python -m unittest discover -s . -p "test_*.py" -v
python kpis.py
python build_pnl_report.py
```

Eleven accounting and statistical checks pass. Source files are unmodified by the later test. All capital, P&L and funding amounts are denominated in USDT. This work uses free historical data and places no live orders.

## KPI and benchmark assessment

The updated PDF includes performance KPIs and dependence-aware significance tests. Key finding: the 2022-2024 12.83% net cumulative return is close to the historical SOFR accrual proxy (12.72%), with no statistically established excess return. The Feb-Dec 2025 carry return of 1.96% trails the SOFR proxy’s 4.01%. The 30-day circular moving-block bootstrap 95% interval for annualized mean daily excess return is [-1.06%, 1.26%] in development and [-2.81%, -1.50%] in the later sample. Conclusions are unchanged for 7-day and 90-day blocks.

Sharpe figures depend on the cash benchmark and sampling frequency. Hourly zero-cash ratios are 3.32 and 3.44; hourly SOFR-excess ratios are 0.03 and -3.53. Daily zero-cash ratios are much larger (11.11 and 9.43), while daily SOFR-excess ratios are 0.09 and -9.68. No unqualified large Sharpe claim is justified. Drawdown measured hourly is 1.12% and 0.11%, respectively, larger than daily-sampled drawdown. Unmodeled venue and stablecoin tail risks remain material.

Benchmarks are spot BTC buy-and-hold and a fixed 20-day long/cash momentum rule with the same spot fee/slippage/lot assumptions. These comparisons are descriptive, not risk-matched or independent validation of an optimized alternative. Results are in results/kpis/. SOFR is a retrospective ACT/360 cash-accrual proxy sourced from the New York Fed; it is not an investable USDT deposit account or the official SOFR Index. USD/USDT parity is assumed.
