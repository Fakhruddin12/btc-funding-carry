# Cost-Aware BTC/ETH Spot-Futures Trading

This directory contains the current BTC/ETH research implementation. Start with the [repository overview](../README.md) for headline results and the [PDF report](deliverables/Quant_Relative_Value_Research.pdf) for the full study. The saved research snapshot is dated 25 October 2026; the publication checks are dated 26 October 2026.

## Research question

A futures premium is not automatically a trading opportunity. The premium must cover fees and slippage on both legs, the income forgone by tying up cash, and the risks of maintaining and unwinding the hedge. The study compares a fixed cost-and-cash entry filter with taking every eligible dated contract. It does not forecast the direction of BTC or ETH.

A separate branch asks whether a funding forecast improves a spot/linear-perpetual strategy. Do not combine its funding receipts, capital, Sharpe or dates with the dated-futures results.

## Dated-futures results

Evaluation: **1 January 2023–26 June 2026**, following a continuous simulation from January 2021.

| Base-cost strategy | Cumulative net return | Annualised compounded return | Daily cash-excess Sharpe | Daily-close max drawdown |
|---|---:|---:|---:|---:|
| Fixed cost-and-cash gate | 19.35% | 5.20% | 0.93 | 0.37% |
| Always-on | 16.81% | 4.55% | 0.01 | 0.69% |
| Cash proxy | 16.79% | 4.55% | Not applicable | See benchmark series |

The gated strategy's **hourly-NAV maximum drawdown is 0.68%**. Its evaluation-period fees are $1,653.90 versus $4,975.44 for always-on, a **66.8% reduction**. Returns include cash interest. The improvement above cash is modest: about 2.57 percentage points cumulative.

| One-way spot / futures cost | Filtered cumulative return | Always-on cumulative return |
|---|---:|---:|
| 12 / 7 basis points | 19.35% | 16.81% |
| 20 / 12 basis points | 18.28% | 13.29% |
| 30 / 20 basis points | 16.79% | 8.69% |

The cash benchmark returns 16.79% over the same evaluation. The entry threshold stays fixed across cost stresses: the stress exercise changes realised trading costs, not the chosen rule.

Sources: [inverse_summary.csv](reports/inverse_summary.csv), [CV risk metrics](reports/cv_risk_metrics.json), [final tables](deliverables/Final_Results.csv), [metric definitions](docs/CV_RISK_METRICS.md).

## Strategy mechanics

### 1. Universe, signal and entry rule

[inverse_download.py](inverse_download.py) enumerates **44 quarterly BTCUSD/ETHUSD expiries**, 2021Q1–2026Q2. BTC contracts have $100 face value and ETH contracts $10. The strategy allows one active maturity per asset, without overlapping maturities.

The decision date is 60 days before expiry. A completed 07:00 UTC close provides the signal for the 08:00 decision; the first scheduled fill is at 09:00. Define the observed basis as:

```text
basis = futures_close / spot_close - 1
hurdle = 2 × (12 + 7) / 10,000 + (cash_rate + 0.02) × holding_days / 365
```

The filter accepts only if the observed basis exceeds this hurdle and the spot signal is executable. The four-leg round trip includes buying and selling spot and opening and closing futures. The additional 2% is an annual risk buffer, not an optimised return target. The always-on comparator uses the same accounting/execution framework without the cost-and-cash basis threshold.

Each accepted asset receives a budget of 40% of current marked NAV, making at most 80% combined. Remaining cash, rejected allocations and unfilled budgets remain unallocated; rejected slots are not redistributed.

### 2. Why the inverse-futures hedge needs coin accounting

For an inverse short with dollar face value C, the coin-denominated unrealised gain at futures price F is:

```text
short_futures_coin_PnL = C × (1/F - 1/F_entry)
matched_coin_collateral = C / F_entry
coin_equity_before_later_fees = C / F
dollar_equity = spot_price × C / F
```

At futures/spot convergence, the frictionless dollar equity tends to C. Before convergence it depends on the spot/futures ratio; matched collateral does not eliminate all basis, collateral or operational risk.

[open_lot](inverse.py) chooses integer contracts and purchases sufficient spot to cover the matched collateral plus coin-denominated entry futures fees. Spot lots round to 0.001 coin. On closure, [close_lot](inverse.py) realises only the closed contracts, charges coin futures fees, sells freed collateral and retains residual coin dust. The ledger never silently converts dust to cash or counts an unrealised futures gain as spendable cash.

### 3. Execution and capacity

Entry is split across 24 hourly opens; the final unwind is split across the 24 hours preceding expiry and ends one hour before expiry. Each leg is constrained to 1% of its **previous 24-hour average hourly notional volume**. The lag prevents current-hour volume from determining its own fill capacity.

Missing executable spot/futures bars cannot generate trades. Flagged mark-price proxies may support valuation, but do not become executable fills. If the exit schedule leaves contracts open, the run is rejected rather than assuming an unlimited terminal fill.

A $1 million initial trial failed a scheduled unwind. The completed prototype starts with **$100,000**, entering the 2023 evaluation at **$108,787.58 NAV**. This is a simulation size, not a verified capacity or live account.

### 4. Costs, cash and portfolio NAV

Base assumed costs are 12 basis points for spot and 7 for futures **per leg, per side**, intended as all-in fee/slippage equivalents. Cost stresses use 20/12 and 30/20.

Hourly NAV equals cash plus the dollar value of coin collateral and inverse-futures unrealised PnL. Fees, interest, residual coins and partial closes are explicitly tracked.

The cash proxy is New York Fed SOFR, available with a seven-calendar-day lag, minus 25 basis points and floored at zero. ACT/360 accrual is converted consistently for hourly accounting. Only eligible unallocated cash earns this assumed return; the same rate constructs the cash benchmark. It is not a realised USDT money-market return.

See [inverse_protocol.json](inverse_protocol.json) for the original declaration and subsequent recorded amendments.

## Separate perpetual-funding experiment

[carry.py](carry.py) buys BTC/ETH spot and shorts matched linear perpetual positions. Unlike dated futures, perpetuals make periodic funding payments whose sign and size vary.

Three declared approaches are compared: always-on, an EWMA funding gate and a Ridge funding forecast. Features include lagged funding estimates, basis, returns, volatility and an ETH indicator. Ridge is refitted quarterly using a trailing window; training excludes 30-day labels that would not have finished by the refit date. Completed information is used before subsequent execution.

The EWMA choice was retained from the original 2022 validation. Later results and corrections had been inspected, so the filenames containing `locked` do **not** establish that the published final evaluation is a pristine unseen test.

At base costs, the 2023–August 2026 perpetual EWMA run returned 18.97%, versus 13.56% for always-on and 17.52% for cash. These belong to a separate $1 million account simulation and a different period. The dated-futures 0.93 Sharpe and 0.68% hourly drawdown must not be attached to this funding result.

[Perpetual results](reports/crypto_locked_summary.csv) · [Selection history](crypto_locked_decision.json) · [Protocol](crypto_protocol.json)

## Data and reproducibility

The packaged frozen inputs contain public historical Binance spot, linear perpetual, funding, inverse-futures and mark-price data; New York Fed SOFR; and inputs for earlier ETF research. Source manifests retain URLs and hashes.

The **19 archive parts** in [inputs/](inputs/) reassemble a snapshot with **139 processed input files**. [extract_inputs.py](extract_inputs.py) checks each part, the complete archive and ZIP integrity, then extracts safely within this directory. [verify_inputs.py](verify_inputs.py) checks all file sizes and SHA-256 hashes against [INPUT_SNAPSHOT.json](INPUT_SNAPSHOT.json).

The original monthly/daily source ZIPs are not duplicated in this GitHub package. Downloaders and manifests remain available, but a fresh download is not necessarily the same data vintage. The full original-release inventory is archived in [docs/ORIGINAL_RELEASE_CONTENTS.json](docs/ORIGINAL_RELEASE_CONTENTS.json); it is a historical inventory, not a promise that all intermediates are tracked here.

### Reproduction workflows

From this directory, create a Python 3.11+ virtual environment and install [requirements.txt](requirements.txt). Then:

```bash
python extract_inputs.py
python verify_inputs.py
python -m pytest -q tests

# Headline dated-futures results, all cost cases, and CV risk metrics:
python inverse.py
python cv_metrics.py

# Separate perpetual-funding runs:
python carry.py --phase development
python carry.py --phase locked

# Additional saved research outputs:
python robustness.py
python diagnostics.py
python build_report.py
```

Run diagnostics after both main branches to cover all 15 strategy ledgers (six dated-futures and nine later-period funding ledgers). Large hourly CSVs are regenerated locally and ignored by Git. Existing summary and audit files document the saved run and are overwritten when their generators are rerun. Preserve a copy or use a separate checkout when comparing results.

## What the tests and diagnostics check

The 31 tests in [tests/](tests/) cover hedge replication, funding timing, fees, cash/NAV identities, partial closes, integer sizing, coin dust, execution/capacity constraints, causal filtering and purged training labels. They check implementation properties; they do not prove that market assumptions are realistic.

[diagnostics.py](diagnostics.py) reconciles NAV and fees against orders, checks information timestamps precede executions, verifies inverse-order participation limits and reports collateral stress. It also calculates 30/90-day block-bootstrap intervals and long-run-variance-adjusted diagnostics. These are important because carry returns are dependent and ordinary daily Sharpe is not a complete risk description.

[Evidence map](RESULTS.md) · [Saved audits](reports/ledger_audits.json) · [Uncertainty diagnostics](reports/dependence_diagnostics.json) · [Original publication checks](docs/PUBLICATION_CHECKS.json)

## Research history and interpretation

The wider project explored ETF mean reversion and perpetual funding before the dated-futures extension. Earlier ETF models failed 2019–2021 validation, and their later strategy test stayed unopened. Earlier equity-pairs results remain failed research and are not headline performance claims.

[trial_ledger.csv](trial_ledger.csv), the protocol JSON files and locked-decision records preserve the sequence of trials and amendments. Preliminary later results were inspected before uniform execution and cash-benchmark corrections. The published results are therefore **retrospective chronological evaluations**, not a prospective test or live trading record.

Hourly opens assume simultaneous leg execution with stated costs. The study does not reconstruct quote depth, queue priority, asynchronous fills, transfer constraints, exchange failure, stablecoin depeg, taxes or ADL. A volume cap is not a market-impact model. OHLC collateral stress checks do not cover every intrahour price path. Most of the headline total return is cash interest, and the small excess return is sensitive to costs.

The source strategy logic and frozen funding identity are retained from the archived snapshot; publication additions document and package the research. No script submits live orders or requires exchange credentials.

## Code and evidence map

| File or directory | Responsibility |
|---|---|
| [inverse.py](inverse.py) | Dated-futures sizing, coin ledger, execution and cost scenarios |
| [carry.py](carry.py) | Linear-perpetual features, forecasts, funding and cash accounting |
| [cv_metrics.py](cv_metrics.py) | Daily cash-excess Sharpe and hourly/daily NAV drawdowns |
| [models.py](models.py), [research.py](research.py) | Earlier state-space and ETF research |
| [robustness.py](robustness.py), [diagnostics.py](diagnostics.py) | Robustness outputs, accounting audits and dependence diagnostics |
| [tests/](tests/) | Implementation checks |
| [reports/](reports/) | Summary CSVs, orders, episodes, manifests and audit results |
| [deliverables/](deliverables/) | PDF, Markdown report, figures and final result table |
| [build_report.py](build_report.py) | Report construction from study outputs |

[Read the full report](deliverables/Research_Report.md) · [Literature review](deliverables/Literature_Review.md) · [Back to project overview](../README.md)
