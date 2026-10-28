# BTC/ETH Spot–Futures Carry Research

**When is the price gap between a cryptocurrency and its futures contract large enough to justify a trade?**

A futures contract can trade above the price of the coin available today. Buying the coin and selling the futures can earn that difference as the contract approaches expiry. The practical question is whether the remaining return pays for trading costs, tied-up capital and the interest available from simply holding cash.

I built a backtest that makes that comparison before entering a trade, then tracks the hedge, collateral, cash flows and execution of both legs. Over **January 2023–26 June 2026**, the strategy returned **19.35% after modelled costs, including cash interest**, compared with **16.81% for entering every eligible contract** and **16.79% for holding the cash proxy**. Most of the total return came from cash interest.

[**Read the study**](relative_value/deliverables/Research_Report.md) · [**Check the numbers**](relative_value/RESULTS.md) · [**Technical implementation**](relative_value/README.md)

## What I built

- A study of **44 quarterly Bitcoin/Ether futures**, including whole-contract sizing and matched coin hedges.
- A trade-entry rule requiring the expected premium to exceed costs, cash opportunity cost and a fixed risk buffer.
- Hourly account records covering fees, cash interest, collateral and the small coin balances left by contract rounding.
- Entry and exit spread across 24 hours, with each order constrained by recent trading volume.
- Cost stresses, accounting checks and dependence-aware uncertainty analysis.

## Results in context

| Measure, Jan 2023–Jun 2026 | Trade only when the return clears the hurdle | Enter every eligible contract | Cash proxy |
|---|---:|---:|---:|
| Total return after modelled costs, including cash interest | **19.35%** | 16.81% | 16.79% |
| Trading costs | **$1,653.90** | $4,975.44 | Not modelled |
| Annualised Sharpe of daily returns above cash | **0.93** | 0.01 | Not applicable |

The trading rule reduced costs by **66.8%** and added about **2.57 percentage points of cumulative return above cash**. Maximum peak-to-trough account loss was **0.68% using hourly account values**, versus 0.37% using daily closing values. Sharpe measures daily excess returns with 365-day annualisation; it is not an hourly risk statistic. [Definitions and risk calculations](relative_value/docs/CV_RISK_METRICS.md).

At the highest assumed trading costs, the strategy effectively matches cash. These are retrospective simulations, not live P&L or evidence of a risk-free opportunity.

![Simulated cumulative returns and drawdowns](relative_value/deliverables/cumulative_returns.png)

## How the backtest works

Sixty days before expiry, the strategy observes the completed-hour futures premium. It buys spot and shorts coin-collateralised inverse futures only if the premium clears round-trip costs, the return forgone on cash and a **2% annual risk buffer**. Entries and exits use 24 hourly slices; each leg is capped at 1% of the previous 24 hours' average hourly notional volume. Rejected or unfilled allocations stay in cash.

The prototype starts with $100,000 in January 2021; its account value entering the 2023 evaluation is $108,787.58. An earlier, larger simulation failed an exit-capacity check and is retained in the research history. [Sizing, hedge derivation and ledger](relative_value/README.md).

## Scope and limitations

The headline study uses **dated futures**, not perpetual-futures funding payments. A separate perpetual-funding experiment and an earlier BTC-only investigation are retained, with their own results. The repository name is historical. [Earlier study guide](docs/EARLIER_FUNDING_STUDY.md).

Hourly prices and assumed costs do not reconstruct order-book fills or market impact. The cash benchmark is a lagged SOFR-based proxy, not an investable stablecoin deposit rate. Exchange default, custody, liquidation under every intrahour price path and operational failures are not fully reconstructed. Some later-period results were seen during development, so this is a retrospective chronological evaluation. [Full assumptions and cost scenarios](relative_value/README.md).

## Reproduce

Python 3.11+; no exchange account or API credentials are needed. From the repository root:

```bash
cd relative_value
python -m pip install -r requirements.txt
python extract_inputs.py
python verify_inputs.py
python -m pytest -q tests
python inverse.py
python cv_metrics.py
```

The supplied input snapshot has 19 checked archive parts containing 139 processed files. Extraction and verification check archive integrity and file hashes. Large hourly output ledgers are regenerated locally. The [27 October verification record](relative_value/docs/VERIFICATION_2026-10-27.md) documents input checks, 31 passing tests and replay of all six dated-futures cases; the separate funding branch was not rerun in that check.

**Author:** Fakhruddin Hakim Hussain · [Portfolio](https://github.com/Fakhruddin12)
