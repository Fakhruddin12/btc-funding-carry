# Cost-aware relative-value trading: research report

Prepared for Fakhruddin Hakim Hussain | 25 October 2026



## Decision

The stronger project is an audited relative-value research engine comparing statistical convergence, perpetual funding and dated-futures basis. The original equity notebook does not support its advertised performance. The ETF pilot failed validation. Two cost-aware crypto carry implementations produced positive later-period net excess returns under explicit assumptions. Neither establishes a durable live edge.



## Final results - all trading costs included

Funding evaluation: 1 January 2023-31 August 2026; 1,000,000 initial USDT capital.

| Model | Total return | CAGR | Cash total return | Daily excess Sharpe | Daily max drawdown |
|---|---:|---:|---:|---:|---:|
| always_on | 13.56% | 3.53% | 17.52% | -3.94 | -0.16% |
| ewma_gate | 18.97% | 4.85% | 17.52% | 2.22 | -0.05% |
| ridge_gate | 18.70% | 4.78% | 17.52% | 1.53 | -0.07% |



Dated evaluation: 1 January 2023-26 June 2026 07:00 UTC; 100,000 initial research book in 2021, with 2023 returns rebased to prior year-end NAV.

| Model | Total return | CAGR | Cash total return | Daily excess Sharpe | Daily max drawdown |
|---|---:|---:|---:|---:|---:|
| always_on | 16.81% | 4.55% | 16.79% | 0.01 | -0.69% |
| cost_cash_gate | 19.35% | 5.20% | 16.79% | 0.93 | -0.37% |



Different evaluation end dates prevent a direct ranking of the two asset/contract designs. Cash is the same lagged SOFR-minus 25 bp proxy within each experiment. Total returns include idle-cash interest.



## Original notebook audit

Full-sample PCA, clustering and pair tests preceded trading on the same period; candidate winners were retained after seeing performance. The ratio was not the fitted cointegrating spread. Signals and fills used the same close. Returns omitted daily unrealised P&L, costs, borrow and consistent terminal closure. A list was mutated during iteration. The notebook printed 39 winners whereas the README said 38. The reviewed code did not calculate the CV Sharpe 1.09. A frozen surviving universe, suspect price jumps and missing borrow data prevent an executable NSE-short backtest claim.



## Statistical convergence pilot

16 economically related ETF pairs,504-session formation, quarterly training-only estimates, next-open execution, distributions, whole shares, borrow and cash accounting. Models: rolling spread, OU cost gate and conditional partial-cointegration state-space cost gate. All three had negative net excess Sharpe in 2019-2021 validation at base costs. The later ETF strategy evaluation stayed unopened.



## Dated-futures mathematics and implementation

Short dollar face C at F 0. Coin P&L at mark Ft equals C(1/Ft-1/F 0). Net initial coin margin q=C/F 0 gives coin equity C/Ft and dollar value C St/Ft before subsequent fees. Match each entry slice using its own futures price. Top up the entry coin fee through a real spot purchase. Integer contracts and rounded spot lots create tiny residual coin dust; retain and mark it. Partial unwinds realise only the closed contracts and release their matching collateral.

All 44 BTC/ETH quarterly contracts from 2021 Q1-2026 Q2 are in the schedule. Entry decision 60 days before expiry, using only a completed prior-hour close; execution starts the next hour over 24 hours. Exit is a 24-hour schedule ending one hour before delivery. Do not substitute an assumed perfect settlement price. Per slice, both legs are capped at 1% of prior 24 hour mean hourly notional volume. Initial 40% capital budget per asset; rejected slots remain cash. No reallocation to the winning asset.

Always-on takes every scheduled contract. The fixed cost/cash gate requires observed basis above conservative four-leg base costs, cash opportunity cost and 2% annual risk buffer. No estimated future funding is substituted into dated returns. At 1 Mcapital, the first development simulation could not unwind 9 ETHcontracts under its participation limit. That failure is retained. The 100 kproof-of-concept is the supported capacity claim.



## Perpetual mathematics and implementation

Buy spot and short exactly the same underlying quantity in a linear perpetual. Price P&L is q[(ST-S 0)-(FT-F 0)]; add actual funding q*mark*rate at each event and subtract costs. Spot and futures are marked separately. Futures unrealised profits are not bank cash. Reserve physical collateral for notional plus unrealised short losses; no interest on reserves. If cash is insufficient after a large price decline, realise futures gains through a paid close/reopen rather than creating free cash.

Compare always-on, conservative min(7 day,30 day)EWMA funding and pooledRidge(alpha 10)forecasts. Ridge predicts next 30 daysfunding with quarterly trailing 730 daytraining, training-only standardisation and exclusion of every future label not completed at fit cutoff. Daily decisions use only available prior information and execute the next hour. Funding is credited to inventory held before the payment. Weekly integer-lot resizing and a high-gross-exposure resize are explicit.

Per asset, target 20% NAVspot plus fully reserved margin. Entry compares 30 daypredictedfunding plusbasis with fees, two-capital-leg cash opportunity cost and 2% annualbuffer. Three weak daily forecasts or adversebasis exit. No reverse carry requiring coin borrowing. Original 2022 validation selectedEWMA; execution and cash-proxy corrections were applied uniformly and the original choice was retained.



## Costs and robustness

All-in one-way base cost: spot 12 bp / futures 7 bp; moderate 20/12; severe 30/20. These are assumptions combining fees and adverse execution, not measured order-book spreads. Stress runs keep the original base-cost decision gate. Every open, resize, forced close and final liquidation is charged. Dated coin fees and extra spot needed to pay them are included.

| Design | Cost spot/futures bp | Total return | Cash total return | CAGR |
|---|---:|---:|---:|---:|
| Funding | 12/7 | 18.97% | 17.52% | 4.85% |
| Funding | 20/12 | 18.53% | 17.52% | 4.74% |
| Funding | 30/20 | 17.91% | 17.52% | 4.59% |
| Dated | 12/7 | 19.35% | 16.79% | 5.20% |
| Dated | 20/12 | 18.28% | 16.79% | 4.93% |
| Dated | 30/20 | 16.79% | 16.79% | 4.55% |



Asset-removal diagnostics retain original slot sizes; unused slots stay cash. Both BTC-only and ETH-only variants had positive excess return at base costs; no asset was reselected. See `leave_one_asset_out.csv`.



## Inference and concentration

| Design | Block length | Annual arithmetic excess mean | 95% block-bootstrap interval | Long-run variance Sharpe | HAC mean p |
|---|---:|---:|---:|---:|---:|
| Funding | 30 | 0.34% | [-0.02%, 0.86%] | 0.76 | 0.144 |
| Funding | 90 | 0.34% | [-0.01%, 0.89%] | 0.72 | 0.169 |
| Dated | 30 | 0.63% | [0.03%, 1.39%] | 0.99 | 0.066 |
| Dated | 90 | 0.63% | [0.11%, 1.32%] | 1.07 | 0.046 |



The funding strategy has only 6 holding episodes in the later period. The dated gate accepts 9 of 28 later asset-expiry decisions; BTC/ETH episodes within a quarter are related, not independent trials. Standard daily Sharpe is not the headline evidence. Small samples, changing regimes and common exchange risk remain. Bootstrap/HAC summaries do not adjust for every discretionary research branch or model selection.



## Audit trail and limits

31 meaningful tests passed.15 final ledgers reconcile NAV, cash, inventory/unrealised P&L, order fees and information-before-execution.962 retained source archives match download-manifestSHA-256 hashes. The pipeline retains raw inputs, exact sourceURLs, processed data and protocols.640 monthly perpetual/spot/funding files plus 264 dated monthlyfiles and 58 dailyrepairs are included.

31 spot-print hours per asset are unavailable over 2020-Aug 2026. A flagged prior spot/mark basis proxy values inventory only; it cannot fill orders. All missing dated mark/execution hours in the declared windows were recovered from official daily archives. A composite-index source was unavailable and was not treated as observed data.

USD futures vsUSDT spot assumes parity. Free off-exchange cash earns the declared proxy; transfers and access to that cash return are not observed. Opening prices plus cost assumptions do not reconstruct executable bid/ask or legging risk. No actual historical order book, queue, ADL or exchange-default series is modelled. The margin stress checks are conditional OHLC diagnostics, not a universal liquidation guarantee. Taxes are excluded.

The later periods are chronological retrospective evaluations. Preliminary later results were seen before fixing an integer-lot execution bug and refining the cash proxy. This is disclosed; do not relabel them pristine unseen holdouts. Pre-correction summaries are retained as superseded audit history, never headline performance.



## What to do next

Freeze these rules and validate with recorded bid/ask and depth, actual fees, order-by-order fills, transfer delays and an independent forward paper ledger. Test a second venue without selecting it for historical returns. Record failed orders and quote-to-fill differences. Reassess expected excess return after custody, stablecoin, cash-access and operational haircuts. More ML or leverage is not the next priority.



## CV positioning

Use Cost-Aware Relative-Value Trading Research rather than claiming a novel arbitrage theorem or guaranteed trading income. Replace the old, unverified pairs-trading performance claims. Suggested bullets:

- Derived matched spot/inverse-futures hedges and tested 44 BTC/ETHquarterly contracts with coin fees, integer sizing and volume-limited execution.

- A fixed cost-and-cash filter raised 2023-Jun 2026 net return to 19.35% from 16.81% always-on, reducing trading costs by 67%.

- Built an audited hourly research engine with causal signals, collateral accounting, cost stresses and 31 tests; assessed performance using block bootstrap and HAC inference.

These are simulated results under declared assumptions. The strongest interview material is the economic mechanism, exact hedge, why the ETF idea failed, the capacity failure and the gap between daily Sharpe and dependence-aware evidence.



## Literature review

The separate Literature_Review.md provides an access-aware review of 11 papers and links to original sources. Downloaded copyrighted paperPDFs are excluded from the deliverable archive.

