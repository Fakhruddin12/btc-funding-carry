# Funding carry: feasibility study

This is a new research direction. Dupire is retained as a separate calibration project; a better risk-neutral local-volatility estimate is not itself evidence of a physical-measure return forecast.

## Economic hypothesis

Buy q BTC spot and short q BTC of the linear BTCUSDT perpetual. Positive funding is paid by longs to shorts; negative funding reverses the cash flow. Define B=P-S, with P the traded perpetual price, S the spot price, M the mark price used for funding, and f a signed settled funding rate. In USDT:

    P&L = q * sum(f_k M_k) + q * (B_entry - B_exit) - trading costs.

This follows directly from spot gain q(S_exit-S_entry) and short gain q(P_entry-P_exit). The spot-directional component cancels for equal fixed BTC quantities. The basis and funding risks remain. Perpetual contracts have no terminal convergence guarantee.

With collateral m*S per BTC in addition to the spot purchase, committed capital is approximately (1+m)*q*S. A positive expected P&L is not sufficient if it fails the opportunity cost of that capital. The economic entry condition over horizon H is:

    E[funding + basis convergence | information available at entry]
      > round-trip costs + y * H * committed capital + risk allowance.

Here y is an explicit cash-hurdle scenario, not an asserted obtainable historical account yield. With m=1, 30 days, y=5% per year, stable prices and zero expected basis change, assumed 38bp round-trip costs require average funding above about 1.34bp per eight-hour payment, before an additional risk allowance. A headline 1bp every eight hours fails that hurdle.

## Frozen baseline for this first check

- BTC only, selected before inspecting carry outcomes.
- Thirty-six non-overlapping monthly holding windows, January 2022 through December 2024. Entry and exit at 01:00 UTC on the first of each month, away from funding boundaries.
- Unconditional long spot / short perpetual. No forecast, market timing, parameter search or selection of profitable months.
- Each monthly episode measured for one BTC per leg; capital denominator is 2*entry spot price. Return-normalized episodes can be scaled to a capital account rebalanced monthly. Round-trip costs are charged every month, including monthly rollover; a more efficient continuous implementation could reduce these costs but requires its own position and collateral simulation.
- Spot taker fee scenario 10bp per execution; perpetual fee scenario 5bp; additional 2bp slippage per leg per execution. These are explicit assumptions, not audited historical fee tiers or measured spreads.
- Trade-price hourly opens proxy execution prices. Hourly mark opens proxy settlement mark prices for funding. This is an economic feasibility test, not a bid/ask executable backtest.
- At entry, cash collateral equal to spot entry notional is assigned to the perpetual leg, with entry costs debited. No borrowing or collateral interest credited. An hourly-high mark stress compares short-account equity against a 1% maintenance-margin scenario. This is not an exchange liquidation engine or an audited historical margin schedule.
- January 2025 archive files are retrieved to provide the final exit and consistent data joins; only the January 1 boundary closes a research holding. No 2025 holding-window performance is assessed. Later 2025 files and all 2026 data are not retrieved.

## What would justify extending this

The unconditional baseline should establish whether there is a material gross transfer to capture and how much survives costs. A subsequent conditional strategy must forecast funding persistence with information available before entry, clear both a capital hurdle and a basis-risk buffer, and control trading turnover. Predicting the sign of funding alone is insufficient.

Use 2022–2024 as development data after this study. Before accessing later outcomes, freeze a small rule family and a sequential evaluation protocol. One candidate is a trailing-30-day mean funding forecast, with a downside bound estimated by a moving-block bootstrap of daily funding. It is a hypothesis, not a validated signal: regime changes can invalidate the historical distribution, and long-run carry evidence does not establish short-horizon predictability. Compare conditional entry against unconditional carry and the explicit cash hurdle. An unseen period must include negative-funding and sharp-rally stress, not merely a favorable bull phase.

Retain rejected and incomplete episodes. Test cost doubling, adverse basis exits, actual exchange maintenance tiers, variation margin, possible collateral transfers, stablecoin depegging, venue/default exposure, and execution during outages. Positive conditional performance must exceed the incremental costs of changing positions. No increase in leverage to repair weak unlevered economics.

## Primary sources

- Binance public historical data and archive conventions: https://github.com/binance/binance-public-data
- Binance funding cash-flow mechanism: https://www.binance.com/en/support/faq/detail/360033525031
- Schmeling, Schrimpf and Todorov, Crypto Carry, BIS Working Paper 1087 (2023): https://www.bis.org/publications/working-paper-1087-crypto-carry

The BIS paper provides an economic rationale and evidence on crypto futures basis, principally fixed-maturity futures. It does not validate this perpetual funding strategy or its return after our assumed costs. The paper explicitly discusses margin and liquidation frictions.

## Reproduction

Run `python study.py`, `python continuous.py`, and `python write_report.py` with numpy and pandas installed. See README.md for the continuous-position results and execution refinement. Cached source ZIPs, source URLs and SHA-256 hashes are retained. Results include monthly accounting and data audits. Data downloads can reflect later archive revisions; source hashes identify the snapshot used. This study checks event timestamps and archive completeness, not historical publication/availability timestamps or contemporaneous account accessibility.

## Interpretation discipline

The previous options entry rule selected zero trades; the negative options P&L was a diagnostic benchmark. The pivot follows the absence of a demonstrated edge and large execution hurdle. A positive result here would be an exploratory feasibility finding, not evidence that switching strategies has solved profitability. We will not choose a rule solely because it turns the historical total green.

## Continuous-position extension

The monthly full-liquidation rule is deliberately an initial cost benchmark. After observing its cost drag, we also tested monthly position resizing with only net BTC quantity changes traded. This retains the unconditional same-venue spot/perpetual hypothesis and avoids redundant monthly crossing. The extension is a post-baseline implementation decision, not an independently selected or validated signal. A new position gets cash collateral equal to its spot notional after rebalancing fees; no borrowing and no interest income are credited. Results remain below a compounded 5% cash hurdle over the full sample.
