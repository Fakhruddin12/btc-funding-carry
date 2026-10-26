# Relative-value trading: literature review and research design

Prepared for Fakhruddin Hakim Hussain, 25 October 2026.

## Research objective

Build a reproducible trading study whose results survive chronological evaluation, execution delays, trading costs and realistic capital accounting. A high historical Sharpe is an outcome to investigate, not a parameter to optimise directly on the final test period.

The original project used PCA and clustering to identify equity pairs. The stronger research question is why a divergence should reverse, how quickly it might reverse, and whether the expected gain pays for implementation. We reviewed two mechanisms: temporary relative-price dislocations, and funding compensation in spot–perpetual pairs.

## What the literature contributes

### 1. Gatev, Goetzmann and Rouwenhorst — Pairs Trading (2006)

The classic distance-based approach supplies a necessary benchmark: form pairs from past price paths and trade them in a later period. The paper also evaluates implementation costs and uses resampling to distinguish pair effects from generic reversal. Its historical profits do not establish that an arbitrary modern pair is profitable. For this project, its value is the experimental structure: separate formation from trading, retain all selected pairs and benchmark a simple rule before adding complexity.

Access reviewed: publication abstract and NBER working-paper summary. [Publication](https://doi.org/10.1093/rfs/hhj020); [working paper](https://www.nber.org/papers/w7032).

### 2. Avellaneda and Lee — Statistical Arbitrage in the US Equities Market (2010; 2009 manuscript)

The authors remove common-factor exposure using PCA or sector ETFs, then model residuals with mean-reverting dynamics. Their framework estimates parameters using prior observations and translates residual deviations into trading decisions. They also examine volume-based modifications and substantial changes in performance across subperiods. This is a stock-versus-factor study, not evidence that two broadly similar ETFs must offer the same edge. Our implication is to model the residual, evaluate forecastable convergence and inspect regime dependence. We do not transfer their historical Sharpe ratios to our implementation.

Access reviewed: full author manuscript, including OU construction and implementation sections. [Author PDF](https://math.nyu.edu/inmemoriam/avellaneda/AvellanedaLeeStatArb20090616.pdf).

### 3. Clegg and Krauss — Pairs Trading with Partial Cointegration (2018)

Partial cointegration allows a spread to contain both a stationary component and a random walk. A Kalman filter can distinguish estimated temporary deviations from persistent changes. This directly addresses a major failure mode of ordinary spread trading: repeatedly betting against a relationship that has shifted. We implemented a conditional-hedge-ratio version, fitting the hedge separately before estimating the state dynamics. This differs from the authors' joint estimation and formal testing procedures. A fitted transient component is not itself evidence of profitable predictability after costs.

Access reviewed: article abstract and the authors' documented implementation; the full working-paper PDF was inaccessible. [Author implementation](https://github.com/matthewclegg/partialCI); [article](https://doi.org/10.1080/14697688.2017.1370122).

### 4. Leung and Li — Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit (2015)

Under an OU spread model, the authors solve entry and liquidation problems with costs and extend the analysis to stop-loss constraints. The optimal policy depends on the model and costs; a larger deviation does not automatically mean a better trade. We take the practical lesson that an entry rule should compare expected convergence with implementation costs and account for adverse exits. Our forecast gate is a simpler heuristic, not a numerical solution of their optimal-stopping problem and not a claim of mathematical optimality.

Access reviewed: full paper, including the stopping formulation. [Author preprint](https://arxiv.org/abs/1411.5062).

### 5. Rad, Low and Faff — Distance, Cointegration and Copula Methods (2016)

This broad empirical comparison is especially useful because it evaluates alternative methods with time-varying trading costs. More elaborate dependence modelling does not automatically produce superior net performance. Profitability and the frequency of opportunities also change over time. Our design therefore compares a small, declared set of methods; includes costs in the decision and the ledger; and reports less successful candidates rather than presenting only the most attractive backtest. We do not add a copula simply to make the project appear more sophisticated.

Access reviewed: full accepted manuscript. [University repository PDF](https://pure.bond.edu.au/ws/portalfiles/portal/36339487/AM_The_profitability_of_pairs_trading_strategies.pdf).

### 6. Bailey and López de Prado — The Deflated Sharpe Ratio (2014)

The paper explains why choosing the best result from many trials inflates apparent performance, with additional complications from non-normal returns. The practical requirement is to retain a trial ledger and disclose the selection process. We froze small model families and used validation before later evaluation. Block-bootstrap intervals and HAC diagnostics address dependence in realised returns, but they do not reconstruct every discretionary research choice. We therefore do not present a mechanically calculated deflated Sharpe as proof that selection bias has disappeared.

Access reviewed: full author manuscript. [Author PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

### 7. Engelberg, Gao and Jagannathan — An Anatomy of Pairs Trading (working paper)

The research connects pair profits to liquidity and the nature of information shocks. The useful distinction is between temporary price pressure or asynchronous reaction to common information, and a lasting change in one asset's value. That motivates our transient/permanent decomposition. Our pilot does not contain a historical news database, so it cannot claim to identify news-driven shocks directly. Price-state estimates are a proxy for the proposed mechanism, not observed labels of its cause.

Access reviewed: abstract; the author PDF could not be downloaded. [Paper abstract](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1330689).

### 8. Schmeling, Schrimpf and Todorov — Crypto Carry (BIS, 2023)

This paper studies the large, variable difference between crypto spot and fixed-maturity futures prices and links it to demand for leveraged exposure and constrained arbitrage capital. It also emphasises margin and liquidation risks. The economic lesson is that compensation must come from somewhere: supplying the other side of leveraged demand can create revenue, but exposes capital to funding and balance-sheet constraints. Our perpetual-funding study is related to this mechanism; it is not a replication of the paper's fixed-maturity strategy, and its historical carry figures are not forecasts for our sample.

Access reviewed: BIS paper and technical sections. [BIS paper](https://www.bis.org/publications/working-paper-1087-crypto-carry).

### 9. He, Manela, Ross and von Wachter — Fundamentals of Perpetual Futures (2022–2026 preprint)

Perpetuals do not have a fixed expiry at which convergence is guaranteed. Funding specifications, transaction costs and arbitrage capacity affect their relationship to spot. The paper studies pricing bounds and implementable trading directions under its assumptions. For our design, the important contribution is the explicit cash-flow mechanism and the need to account for collateral. We test measured funding receipts, changes in the basis and implementation costs separately. Our forecasting gate is not the paper's theoretical arbitrage strategy, and exchange solvency remains outside the price backtest.

Access reviewed: current full-text HTML, including pricing and implementation discussions. [Preprint](https://arxiv.org/abs/2212.06888).

### 10. Ackerer, Hugonnier and Jermann — Perpetual Futures Pricing (2023–2024 preprint)

The authors derive pricing results for several perpetual-contract specifications. Their analysis shows that the funding rule and the currencies of settlement matter. We use linear USDT-margined contracts so that the spot and futures legs can be matched in underlying units, and include funding as a distinct cash flow. We do not substitute a fixed-maturity basis formula for perpetual valuation or assume that every positive premium is an arbitrage. The project remains an empirical strategy study rather than a new perpetual-pricing theorem.

Access reviewed: full-text HTML. [Preprint](https://arxiv.org/abs/2310.11771).

## The first test: transient versus permanent relative-price movements

For log prices, consider

\[
\log P_{A,t}=\alpha+\beta\log P_{B,t}+M_t+R_t,
\qquad M_t=\rho M_{t-1}+\epsilon^M_t,
\qquad R_t=R_{t-1}+\epsilon^R_t.
\]

We fit the regression and state parameters using a prior formation window, then update filtered states causally. A smoothed state would incorporate later observations and must not drive trading. An estimated temporary displacement implies an approximate H-session convergence of \(-M_t(1-\rho^H)\). Dividing by gross hedge weights translates this into a first-order return estimate. Our conservative gate subtracts one posterior state standard error before comparing the estimate with costs. This margin excludes parameter uncertainty and is not a confidence guarantee.

The pilot used 16 economically related ETF pairs, a 504-session formation window, quarterly refits, next-open fills, cash distributions, whole shares, borrow charges and a cash benchmark. It compared ordinary spread signals, an OU cost gate and a partial-cointegration cost gate. All three had negative net excess Sharpe in the 2019–2021 validation period at the base cost assumptions. The subsequent ETF strategy test was therefore left unopened. The price data was downloaded for reproducibility, but no later strategy-performance result was used to select a favourable period.

This rejects these implementations on this dataset. It does not prove that partial cointegration or all ETF relative-value strategies are unprofitable. A plausible interpretation is that much of the small daily divergence has disappeared before a delayed opening trade can capture it. That interpretation requires higher-frequency quote evidence to establish causally.

## The stronger economic anchor: spot–perpetual funding carry

A long spot position and an equal-unit short linear perpetual position reference the same asset. For constant quantity between adjustments, terminal price P&L is

\[
\Pi_T=q[(S_T-S_0)-(F_T-F_0)]
       +\sum_{\tau}q\,M_\tau f_\tau-\text{costs}.
\]

The first term is a change in the spot–perpetual price gap. The second is actual funding cash flow, using the settlement mark and funding rate. Common directional price movements largely cancel; funding, the basis and execution remain. There is no guarantee of convergence at a particular date.

The tested incremental question is whether causal forecasts and no-trade bands improve on continuously collecting carry. We compare always-on carry, a conservative EWMA gate and a regularised funding forecast. The forecast target is the next 30 calendar days of funding; training excludes every label whose future window has not ended before the fit date. This is a 30-day purge, not merely a train/test row split.

Capital accounting matters as much as the forecast. With one unit of spot notional and one unit of reserved futures collateral, the strategy commits approximately two units of capital. A funding yield of 10% on one leg is therefore not a 10% return on all committed capital. Entry compares expected funding and the observed basis with both-leg fees, cash opportunity cost and a declared risk buffer. Short collateral and unrealised futures gains do not earn bank interest in the ledger.

## What would count as convincing evidence

1. Positive net returns relative to the stated cash proxy in a later period not used to alter the rules.
2. A comparison against the always-on economic benchmark, not only against an intentionally weak statistical rule.
3. Returns attributable to measured funding and basis P&L, with every trading fee and inventory adjustment included.
4. Acceptable behaviour during negative-funding and stressed-market episodes, with no ignored margin breaches.
5. Sensitivity to worse fills and costs, plus uncertainty estimates that preserve blocks of dependent observations.
6. A clear boundary between historical simulation and unmeasured exchange, stablecoin, transfer and order-book risks.

The work can be a strong quant CV project if these conditions produce defensible results. Its value would be economic reasoning, time-series forecasting, event-time accounting and careful validation. It would not need a claim that the basic trading idea is novel.

## Data and implementation sources

- [Official Binance public-data documentation](https://github.com/binance/binance-public-data): archive layouts and the 2025 spot timestamp-unit change.
- [Official funding-rate history API specification](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data): funding events and mark-price semantics.
- [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html): historical cash and factor proxies.
- `research_protocol.json` and `crypto_protocol.json`: declared assumptions, universes and evaluation rules.
- `source` manifests: exact download URLs, retained raw archives and SHA-256 hashes.

Missing monthly mark bars were recovered from official daily archives. Unavailable spot-print hours use a flagged previous-basis/mark valuation proxy and cannot execute. Actual funding rates are observed; hourly mark prices approximate the mark at settlement when archive timestamps contain millisecond jitter. OHLC opening prices with explicit slippage are execution assumptions, not observed executable bid/ask quotes. USDT returns are not automatically USD returns. These limitations must remain visible in any results report.

## Dated inverse-futures extension

The fixed-maturity study is closer to the BIS carry mechanism than the perpetual study. For a short inverse futures position with dollar face C, entry price F 0 and mark Ft, coin-denominated P&L is C(1/Ft - 1/F 0). Buy net coin collateral q=C/F 0 after entry fees. The marked coin equity is then C/Ft, worth C St/Ft in spot currency. At ideal convergence FT=ST it becomes C, before exit fees. This is a replication identity under the contract assumptions, not a guarantee against exchange failure or execution mismatch. In the actual backtest we close before delivery and retain the observed residual basis.

We tested every BTC/ETH quarterly expiry from 2021 Q1 through 2026 Q2, using a declared 60-day entry horizon and 24-hour volume-limited entry/exit schedules. A 1 M trial failed an exit-capacity check in development; the documented 100 k implementation passed. Integer contracts, coin-denominated fees and retained spot-lot dust are explicit. No horizon or asset was selected from later returns.

Official specifications: [inverse P&L](https://www.binance.com/en/support/faq/detail/3a55a23768cb416fb404f06ffedde4b2); [contract faces and collateral](https://www.binance.com/en/support/faq/detail/85eac2bba0b342819122dc9bd4745e9b); [delivery convention](https://www.binance.com/en-BH/support/faq/detail/a3401595e1734084959c61491bc0dbe3).

## Dependence and the cash benchmark

Lo (2002) motivates correcting inference for serial dependence. We use Bartlett HAC long-run variance at 30/90 daily lags and 2000 circular-block bootstrap samples at 30/90 days. These are diagnostics, not proof that all selection risk has been removed. [Publication](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios). Access reviewed: publication abstract.

The final crypto results use the official NYFed SOFR series, seven calendar days after its effective date, minus a 25 bp cash-management spread with floor zero; ACT 360 accrual. This replaces the overly coarse rounded daily Fama-French RF proxy. The original ETF pilot still uses its declared Fama-French benchmark. Free off-exchange cash is assumed able to earn the reference return; posted collateral earns none. The cash return is a proxy, not an observed investable fund return. [NYFed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr).

## Final empirical assessment

See the accompanying research report and final summary CSVs for audited results. Both cost-aware carry approaches improve on continuous carry under base assumptions. Their excess returns are modest, regime-concentrated and sensitive to frictions and unpriced exchange risk. This supports a quant research prototype, not a claim of proven live profitability. Execution/accounting and cash-proxy corrections occurred after preliminary later results had been seen; the evaluation is retrospective and chronological, not a pristine unseen test.
