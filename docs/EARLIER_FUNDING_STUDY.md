# BTC Funding Carry: A Cash-Ledger Feasibility Study
### Testing a simple market-neutral idea against costs and a cash benchmark

## Included saved artifacts

[market-data-snapshots.zip](../market-data-snapshots.zip) contains 204 original saved files. Extract it at the repository root before using the archived arrays or data snapshots:

```bash
python -m zipfile -e market-data-snapshots.zip .
```

Paths and SHA-256 hashes are recorded in [ARTIFACTS.json](../ARTIFACTS.json). Source code, figures and result tables remain directly browsable.

**Question:** Does holding spot BTC against a short perpetual position earn an economically meaningful return after fees, slippage, rebalancing and collateral accounting?

**Finding:** The simulated strategy made positive net P&L, but did **not** establish excess return over a historical SOFR cash-accrual proxy. The later 2025 period underperformed that proxy. This is a feasibility and accounting study, with no fitted entry signal.

| Result | 2022–2024 development | Feb–Dec 2025 later test |
|---|---:|---:|
| Starting capital | 10,000 USDT | 10,000 USDT |
| Net P&L | 1,283.11 USDT | 195.70 USDT |
| Net cumulative return | 12.83% | 1.96% |
| Historical SOFR proxy return | 12.72% | 4.01% |

[**Full report**](../output/pdf/Funding_carry_PnL_report.pdf) · [**Cash-ledger results**](../results/pnl/) · [**Benchmark and statistical checks**](../results/kpis/) · [**Methods**](../docs/ORIGINAL_RESEARCH_NOTES.md)

## Research contribution

- Separate spot, perpetual, funding, fee, slippage and cash accounting.
- Actual cash constraints, 0.001 BTC research lots and marked valuations.
- A frozen protocol before the later sample, plus explicit reporting changes.
- Cost stress tests and hourly drawdown measurement.
- Dependence-aware moving-block bootstrap and cash-benchmark comparison.
- Eleven accounting and statistical checks.

The two periods begin as separate accounts and finish with positions closed. The later period is not a continuation through January 2025. Large zero-cash Sharpe ratios are not headline evidence: the result changes substantially when assessed relative to the cash proxy.

## Reproduce

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s . -p "test_*.py" -v
python study.py
python continuous.py
python pnl.py
python pnl.py --validation
python kpis.py
```

Public source archives and checksum manifests are retained for offline reproducibility. Hourly execution and mark proxies, assumed costs, USD/USDT parity, venue risk and stablecoin risk limit the conclusions. The SOFR accrual series is a retrospective benchmark, not an investable USDT deposit.

**Author:** Fakhruddin Hakim Hussain · [Portfolio](https://github.com/Fakhruddin12)

