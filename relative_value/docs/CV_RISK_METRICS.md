# CV Risk Metrics: Dated BTC/ETH Futures

These numbers concern the fixed cost-and-cash entry filter for dated futures. They do not describe the separate perpetual-funding study.

| Metric | January 2023-June 2026 evaluation |
|---|---:|
| Net cumulative return, including cash interest | 19.35% |
| Always-on net cumulative return | 16.81% |
| Cash-proxy cumulative return | 16.79% |
| Net annualised return | 5.20% |
| Annualised Sharpe of daily returns above the cash proxy | 0.93 |
| Maximum drawdown sampled on hourly NAV | 0.68% |
| Maximum drawdown sampled on daily-close NAV | 0.37% |

## Definitions and reproduction

After extracting the inputs, run `python inverse.py`, then `python cv_metrics.py`, from `relative_value/`. The script writes [the saved metrics](../reports/cv_risk_metrics.json). The summary returns are in [inverse_summary.csv](../reports/inverse_summary.csv).

Daily excess return is strategy daily net return minus the compounded daily cash-proxy return. Sharpe equals the mean daily excess return divided by its sample standard deviation, multiplied by the square root of 365. It uses daily returns even though drawdown is also inspected hourly. The cash proxy is lagged SOFR minus 25 basis points, floored at zero. It is a benchmark assumption, not an investable USDT account.

Maximum drawdown is the largest peak-to-trough decline in portfolio NAV within the stated evaluation, including the evaluation's initial NAV. The 0.68% number uses every hourly observation; 0.37% uses only daily closes. Neither is a maximum one-hour loss. The dependence-adjusted Sharpe diagnostics and bootstrap intervals remain in [dependence_diagnostics.json](../reports/dependence_diagnostics.json).

## Capital, capacity and interpretation

The full simulation starts in January 2021 with USD 100,000. Its NAV entering the January 2023 evaluation is USD 108,787.58; the later-period return is measured relative to that starting NAV. The CV's USD 100k describes the original simulated account. It is not a proven capacity limit or live AUM. An earlier USD 1 million test failed a scheduled unwind check.

Orders are capped at 1% of prior mean hourly volume. That conditional volume check does not establish historical order-book depth, simultaneous fills, transfer feasibility or large-capital capacity. The strategy buys spot and shorts coin-collateralised inverse futures; it does not finance itself by borrowing spot. Costs and the cash benchmark are explicit assumptions. Exchange default, stablecoin depeg, ADL, taxes and transfer risks are not reconstructed.

The contribution is an accounting- and cost-aware evaluation of a known carry mechanism. The results are retrospective chronological simulations, not live trading, a pristine untouched holdout, or proof of persistent alpha.
