# Results and Verification

The headline results describe the dated BTC/ETH futures strategy. The separate funding experiment has different dates, capital and results.

| Result or implementation detail | Where to verify |
|---|---|
| 44 quarterly contracts | `inverse_download.py`, `inverse_data/contracts.json` after input extraction and `reports/inverse_data_audit.csv` |
| Entry hurdle based on premium, costs and cash | `inverse.py` and `inverse_protocol.json` |
| Hourly orders and 1% volume cap | `inverse.py` load/schedule logic and saved `reports/inverse_*_orders.csv` |
| 19.35% net total return versus 16.81% without the filter | `reports/inverse_summary.csv` and `deliverables/Final_Results.csv`, January 2023-June 2026 |
| 5.20% annualised return versus 4.55% cash | Same final tables, with the benchmark construction in `carry.py` |
| 67% lower trading costs | Compare filtered and always-on base-cost rows in `reports/inverse_summary.csv` |
| 31 tests | `tests/` and `reports/test_results.txt` |
| Ledger reconciliation | `reports/ledger_audits.json` |

The full report derives the inverse-contract hedge and explains costs, collateral, capacity, uncertainty and selection history. Total return includes interest on unallocated cash. The later evaluation is retrospective and chronological, rather than a pristine untouched holdout. There is no live-return claim.

The full processed input snapshot is distributed with its hashes. Extract it and run `verify_inputs.py` before reproduction. Running the backtests recreates the larger hourly ledgers.
