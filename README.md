# BTC/ETH Spot-Futures Trading Research

I tested whether buying spot BTC/ETH and shorting futures can earn enough to cover execution costs and the return available on cash. The latest study compares a fixed entry rule with taking every eligible trade.

**Main result:** the dated-futures backtest returned **19.35% after costs** over January 2023-June 2026, compared with **16.81%** without the entry filter. Annualised returns were **5.20% versus 4.55% for cash**, and trading costs were **67% lower**. Most of the total return came from cash interest. The excess return is modest and these are retrospective simulations.

[Latest research and reproduction steps](relative_value/) | [Full report](relative_value/deliverables/Quant_Relative_Value_Research.pdf) | [Result tables](relative_value/deliverables/Final_Results.csv) | [Tests](relative_value/tests/)

![Cumulative returns and drawdowns](relative_value/deliverables/cumulative_returns.png)

## What the project contains

- An inverse-contract hedge with coin fees, integer contract sizes and retained coin dust.
- Hourly execution with a 1% participation limit based on prior mean hourly volume.
- A fixed entry rule that compares the futures premium with costs, cash returns and a risk buffer.
- A comparison of 44 BTC/ETH quarterly contracts across the wider 2021Q1-2026Q2 research sample.
- Funding-carry comparisons, cost stresses, block-bootstrap intervals and dependence-adjusted statistics.
- 31 accounting, timing and implementation tests, plus saved ledger audits.

The supported dated-futures prototype starts with USD 100,000. An earlier USD 1 million trial failed an unwind-capacity check and is retained as a failure case. Historical order-book depth, transfers and exchange default are outside this backtest.

## Verify the results

Start with [the evidence map](relative_value/RESULTS.md). It links the headline figures to saved tables, implementation files and test evidence.

The complete processed input snapshot is included as verified archive parts under `relative_value/inputs/`. Run `python extract_inputs.py` from `relative_value/` to reassemble and extract it before running the code. Source URLs and hashes are included. The research files do not place live orders or require exchange credentials.

## Research history

The [latest study](relative_value/) extends the earlier BTC-only funding feasibility study with BTC/ETH, entry filters, dated futures and more detailed accounting. The earlier files remain at the repository root. [The earlier README](docs/EARLIER_FUNDING_STUDY.md) describes those historical results. Use the files under `relative_value/` for the current results.

**Author:** Fakhruddin Hakim Hussain | [GitHub profile](https://github.com/Fakhruddin12)
