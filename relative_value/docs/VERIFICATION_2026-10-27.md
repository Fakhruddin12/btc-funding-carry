# Verification — 27 October 2026

Verified the published repository at commit `26b1e90cb934924fa6daa6979269112a097dddc1` before the documentation update.

## Executed checks

- Reassembled and verified all 19 archive parts with `extract_inputs.py`.
- Verified all 139 processed input files against `INPUT_SNAPSHOT.json`.
- Ran `python -m pytest -q tests`: **31 passed**.
- Reran `inverse.py`: both dated-futures strategies at 12/7, 20/12 and 30/20 basis-point costs.
- Reran `cv_metrics.py`: the saved Sharpe and drawdown JSON reproduced exactly.
- Regenerated inverse summary, order/episode records, source/protocol identity and data audit matched the committed files byte for byte (no tracked result changes).
- Independently checked all six regenerated hourly inverse ledgers: 48,056 observations each; positive cash; NAV reconciliation; fee/order reconciliation; information-before-fill timestamps; participation limits. Largest NAV identity residual: 4.37e-11 USD.

## Reproduced headline values

| Metric | Value |
|---|---:|
| Later-period start | 1 January 2023 |
| Later-period end | 26 June 2026, 07:00 UTC |
| Filtered cumulative net return | 19.3538534651% |
| Always-on cumulative net return | 16.8065730508% |
| Cash-proxy cumulative return | 16.7857740966% |
| Filtered annualised compounded return | 5.2036660283% |
| Annualised daily cash-excess Sharpe | 0.9295030367 |
| Hourly-NAV maximum drawdown | 0.6798096398% |
| Daily-close maximum drawdown | 0.3732757149% |
| Filtered / always-on evaluation fees | $1,653.901348 / $4,975.443498 |
| Fee reduction | 66.7587150961% |

## Scope and environment

Python 3.12.14; NumPy 2.3.5; pandas 2.2.3; SciPy 1.17.0; scikit-learn 1.8.0; statsmodels 0.15.0; pytest 9.1.1.

This verification reran the headline **dated-futures** branch and the full 31-test suite. The separate perpetual-funding branch, earlier BTC-only root study and report generation were not rerun in this check; their existing published results and earlier audit records remain available. No trading logic or result values were edited.

This confirms reproducibility under the published data and modelling assumptions. It does not validate historical fills, an investable cash rate, omitted counterparty risks, live profitability or capacity.
