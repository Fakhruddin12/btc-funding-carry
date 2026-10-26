"""Build the research report and static scientific figures from audited outputs."""
from pathlib import Path
import json,re,html
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

ROOT=Path(__file__).parent;OUT=ROOT/'deliverables';OUT.mkdir(exist_ok=True)
REP=ROOT/'reports'
crypto=pd.read_csv(REP/'crypto_locked_summary.csv');dated=pd.read_csv(REP/'inverse_summary.csv')
cf=crypto[(crypto.model=='ewma_gate')&(crypto.spot_bps==12)].iloc[0]
cb=crypto[(crypto.model=='always_on')&(crypto.spot_bps==12)].iloc[0]
df=dated[(dated.model=='cost_cash_gate')&(dated.spot_bps==12)&(dated.period=='later')].iloc[0]
db=dated[(dated.model=='always_on')&(dated.spot_bps==12)&(dated.period=='later')].iloc[0]
diags=json.loads((REP/'dependence_diagnostics.json').read_text())
audit=json.loads((REP/'ledger_audits.json').read_text());assert len(audit)==15
D={r['file']:r for r in diags}
ch=pd.read_csv(REP/'crypto_locked_ewma_gate_cost12_7_hourly.csv',index_col=0,parse_dates=True)
dh=pd.read_csv(REP/'inverse_cost_cash_gate_cost12_7_hourly.csv',index_col=0,parse_dates=True)
episodes=pd.read_csv(REP/'crypto_locked_ewma_gate_cost12_7_episodes.csv')
de=pd.read_csv(REP/'inverse_cost_cash_gate_cost12_7_episodes.csv');later_de=de[pd.to_datetime(de.decision).dt.year>=2023]
robust=pd.read_csv(REP/'leave_one_asset_out.csv')
P=lambda x:f'{100*x:.2f}%'
F=lambda x:f'{x:,.0f}'
CASH=lambda row:(1+row.cash_return)**(365/row.days)-1

def tidy_text(text):
    links=[]
    def protect(match):
        links.append(match.group());return 'URLPLACEHOLDER'+chr(65+len(links)-1)
    text=re.sub(r'https?://[^\s)]+',protect,text)
    text=re.sub(r'(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])|(?<=%)(?=[a-zA-Z])',' ',text)
    for a,b in [('Q 1','Q1'),('Q 2','Q2'),('Q 3','Q3'),('Q 4','Q4'),('SHA 256','SHA-256'),
                ('USDfutures','USD futures'),('USDTspot','USDT spot'),('bp/futures','bp / futures'),
                ('monthlyperpetual','monthly perpetual'),('datedmonthly','dated monthly'),
                ('cash Source','cash source'),('See leave_one_asset_out.csv','See `leave_one_asset_out.csv`')]:
        text=text.replace(a,b)
    for i,url in enumerate(links):text=text.replace('URLPLACEHOLDER'+chr(65+i),url)
    return text

# Figures: both plots keep their own full declared evaluation periods.
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,1,figsize=(9,7.1),layout='constrained')
for ax,stem,strategies,start,initial,title in [
 (axes[0],'crypto_locked_', [('always_on','Always on','#9a7187'),('ewma_gate','Funding gate','#137a72')],'2023',1e6,'Funding carry | Jan 2023-Aug 2026'),
 (axes[1],'inverse_', [('always_on','Always on','#9a7187'),('cost_cash_gate','Cost + cash gate','#137a72')],'2023',None,'Dated-futures carry | Jan 2023-Jun 2026')]:
 for model,label,color in strategies:
  h=pd.read_csv(REP/f'{stem}{model}_cost12_7_hourly.csv',index_col=0,parse_dates=True)
  base=initial if initial is not None else h.loc[:'2022'].nav.iloc[-1]
  h=h.loc[start:];nav=h.nav.resample('D').last()/base-1
  ax.plot(nav.index,nav,label=label,color=color,linewidth=1.8)
 cash=(1+h.cash_benchmark_return).resample('D').prod().cumprod()-1
 ax.plot(cash.index,cash,label='SOFR - 25bp cash proxy',color='#25354d',ls='--',lw=1.4)
 ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_title(title,loc='left',fontweight='bold');ax.grid(alpha=.15)
 ax.legend(loc='upper left',fontsize=8,frameon=False)
fig.savefig(OUT/'cumulative_returns.png',dpi=190);plt.close(fig)

fig,ax=plt.subplots(figsize=(9,3.0),layout='constrained')
for i,(file,label) in enumerate([('crypto_locked_ewma_gate_cost12_7_hourly.csv','Funding gate'),('inverse_cost_cash_gate_cost12_7_hourly.csv','Dated-futures gate')]):
 for j,b in enumerate([30,90]):
  d=next(q for q in D[file]['diagnostics'] if q['block_days']==b);v=d['annual_arithmetic_excess'];lo,hi=d['bootstrap95_annual_mean']
  ax.errorbar(v,i+(j-.5)*.17,xerr=[[v-lo],[hi-v]],fmt='o',capsize=4,color=['#137a72','#597bb2'][j],label=f'{b}-day blocks' if i==0 else None)
ax.axvline(0,color='#666',ls='--',lw=1);ax.set_yticks([0,1],['Funding gate','Dated-futures gate']);ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Annual arithmetic return above cash: mean and 95% circular-block bootstrap interval')
ax.legend(frameon=False,fontsize=8);ax.grid(axis='x',alpha=.15);fig.savefig(OUT/'uncertainty.png',dpi=190);plt.close(fig)

# Bibliography and an access-aware, short synthesis for the PDF.
refs=[
('Gatev, Goetzmann & Rouwenhorst (2006)','Separate historical pair formation from subsequent trading. Distance rules are benchmarks, not proof of a present-day edge.','https://www.nber.org/papers/w7032','Abstract/working-paper summary'),
('Avellaneda & Lee (2010; 2009 manuscript)','Model factor-adjusted residuals rather than arbitrary price ratios; inspect changing regimes and implementation costs.','https://math.nyu.edu/inmemoriam/avellaneda/AvellanedaLeeStatArb20090616.pdf','Full author manuscript'),
('Clegg & Krauss (2018)','Allow temporary mean reversion alongside permanent relationship shifts. Our conditional hedge fit is simpler than their joint procedure.','https://doi.org/10.1080/14697688.2017.1370122','Abstract + author implementation'),
('Leung & Li (2015)','Entry and liquidation depend on costs and stopping rules. Our cost gate is a heuristic, not their optimal-stopping solution.','https://arxiv.org/abs/1411.5062','Full author preprint'),
('Rad, Low & Faff (2016)','Compare simple and complex dependence models after time-varying costs. More elaborate models need empirical justification.','https://pure.bond.edu.au/ws/portalfiles/portal/36339487/AM_The_profitability_of_pairs_trading_strategies.pdf','Full accepted manuscript'),
('Bailey & Lopez de Prado (2014)','Record trials and selection. A best observed Sharpe is inflated by research choices; no automatic correction erases all discretion.','https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf','Full author manuscript'),
('Engelberg, Gao & Jagannathan','Temporary liquidity pressure differs from permanent information. Price filters do not reveal the cause of a shock without news data.','https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1330689','Abstract only'),
('Schmeling, Schrimpf & Todorov (BIS, 2023)','Carry compensates constrained arbitrage capital. Dated-futures basis has a different convergence mechanism from perpetual funding.','https://www.bis.org/publications/working-paper-1087-crypto-carry','Full BIS paper'),
('He, Manela, Ross & von Wachter','Perpetual pricing depends on funding rules, costs and arbitrage capacity. Positive funding is not a fixed-maturity payoff guarantee.','https://arxiv.org/abs/2212.06888','Full-text preprint HTML'),
('Ackerer, Hugonnier & Jermann','Contract denomination and funding specifications matter; linear and inverse contracts require different cash-flow ledgers.','https://arxiv.org/abs/2310.11771','Full-text preprint HTML'),
('Lo (2002)','Serial dependence changes Sharpe annualisation. Report a long-run-variance diagnostic and block uncertainty alongside the usual daily statistic.','https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios','Publication abstract')]

# Extend the full review without overwriting the original access-level disclosures.
lit=(ROOT/'LITERATURE_REVIEW.md').read_text()
if '\n## Dated inverse-futures extension' not in lit:
 lit+='''\n## Dated inverse-futures extension\n\nThe fixed-maturity study is closer to the BIS carry mechanism than the perpetual study. For a short inverse futures position with dollar face C, entry price F0 and mark Ft, coin-denominated P&L is C(1/Ft - 1/F0). Buy net coin collateral q=C/F0 after entry fees. The marked coin equity is then C/Ft, worth C St/Ft in spot currency. At ideal convergence FT=ST it becomes C, before exit fees. This is a replication identity under the contract assumptions, not a guarantee against exchange failure or execution mismatch. In the actual backtest we close before delivery and retain the observed residual basis.\n\nWe tested every BTC/ETH quarterly expiry from2021Q1 through2026Q2, using a declared60-day entry horizon and24-hour volume-limited entry/exit schedules. A1M trial failed an exit-capacity check in development; the documented100k implementation passed. Integer contracts, coin-denominated fees and retained spot-lot dust are explicit. No horizon or asset was selected from later returns.\n\nOfficial specifications: [inverse P&L](https://www.binance.com/en/support/faq/detail/3a55a23768cb416fb404f06ffedde4b2); [contract faces and collateral](https://www.binance.com/en/support/faq/detail/85eac2bba0b342819122dc9bd4745e9b); [delivery convention](https://www.binance.com/en-BH/support/faq/detail/a3401595e1734084959c61491bc0dbe3).\n\n## Dependence and the cash benchmark\n\nLo (2002) motivates correcting inference for serial dependence. We use Bartlett HAC long-run variance at30/90daily lags and2000circular-block bootstrap samples at30/90days. These are diagnostics, not proof that all selection risk has been removed. [Publication](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios). Access reviewed: publication abstract.\n\nThe final crypto results use the official NYFed SOFR series, seven calendar days after its effective date, minus a25bp cash-management spread with floor zero; ACT360 accrual. This replaces the overly coarse rounded daily Fama-French RF proxy. The original ETF pilot still uses its declared Fama-French benchmark. Free off-exchange cash is assumed able to earn the reference return; posted collateral earns none. The cash return is a proxy, not an observed investable fund return. [NYFed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr).\n\n## Final empirical assessment\n\nSee the accompanying research report and final summary CSVs for audited results. Both cost-aware carry approaches improve on continuous carry under base assumptions. Their excess returns are modest, regime-concentrated and sensitive to frictions and unpriced exchange risk. This supports a quant research prototype, not a claim of proven live profitability. Execution/accounting and cash-proxy corrections occurred after preliminary later results had been seen; the evaluation is retrospective and chronological, not a pristine unseen test.\n'''
 lit=tidy_text(lit)
 (ROOT/'LITERATURE_REVIEW.md').write_text(lit)
lit=tidy_text(lit)
(ROOT/'LITERATURE_REVIEW.md').write_text(lit)
(OUT/'Literature_Review.md').write_text(lit)

# A standalone, detailed report in Markdown, preserving tables for reuse.
lines=['# Cost-aware relative-value trading: research report','Prepared for Fakhruddin Hakim Hussain | 25 October 2026','',
'## Decision',
'The stronger project is an audited relative-value research engine comparing statistical convergence, perpetual funding and dated-futures basis. The original equity notebook does not support its advertised performance. The ETF pilot failed validation. Two cost-aware crypto carry implementations produced positive later-period net excess returns under explicit assumptions. Neither establishes a durable live edge.',
'', '## Final results - all trading costs included',
'Funding evaluation: 1 January 2023-31 August 2026; 1,000,000 initial USDT capital.',
'| Model | Total return | CAGR | Cash total return | Daily excess Sharpe | Daily max drawdown |', '|---|---:|---:|---:|---:|---:|']
for model in ['always_on','ewma_gate','ridge_gate']:
 r=crypto[(crypto.model==model)&(crypto.spot_bps==12)].iloc[0];lines.append(f'| {model} | {P(r.total_return)} | {P(r.cagr)} | {P(r.cash_return)} | {r.excess_sharpe:.2f} | {P(r.max_drawdown_daily)} |')
lines+=['','Dated evaluation: 1 January 2023-26 June 2026 07:00 UTC; 100,000 initial research book in2021, with2023 returns rebased to prior year-end NAV.','| Model | Total return | CAGR | Cash total return | Daily excess Sharpe | Daily max drawdown |','|---|---:|---:|---:|---:|---:|']
for r in [db,df]:lines.append(f'| {r.model} | {P(r.total_return)} | {P(r.cagr)} | {P(r.cash_return)} | {r.excess_sharpe:.2f} | {P(r.max_drawdown_daily)} |')
lines+=['','Different evaluation end dates prevent a direct ranking of the two asset/contract designs. Cash is the same lagged SOFR-minus25bp proxy within each experiment. Total returns include idle-cash interest.','',
'## Original notebook audit',
'Full-sample PCA, clustering and pair tests preceded trading on the same period; candidate winners were retained after seeing performance. The ratio was not the fitted cointegrating spread. Signals and fills used the same close. Returns omitted daily unrealised P&L, costs, borrow and consistent terminal closure. A list was mutated during iteration. The notebook printed39winners whereas the README said38. The reviewed code did not calculate the CV Sharpe1.09. A frozen surviving universe, suspect price jumps and missing borrow data prevent an executable NSE-short backtest claim.',
'', '## Statistical convergence pilot',
'16 economically related ETF pairs,504-session formation, quarterly training-only estimates, next-open execution, distributions, whole shares, borrow and cash accounting. Models: rolling spread, OU cost gate and conditional partial-cointegration state-space cost gate. All three had negative net excess Sharpe in2019-2021 validation at base costs. The later ETF strategy evaluation stayed unopened.',
'', '## Dated-futures mathematics and implementation',
'Short dollar face C at F0. Coin P&L at mark Ft equals C(1/Ft-1/F0). Net initial coin margin q=C/F0 gives coin equity C/Ft and dollar value C St/Ft before subsequent fees. Match each entry slice using its own futures price. Top up the entry coin fee through a real spot purchase. Integer contracts and rounded spot lots create tiny residual coin dust; retain and mark it. Partial unwinds realise only the closed contracts and release their matching collateral.',
'All44BTC/ETH quarterly contracts from2021Q1-2026Q2 are in the schedule. Entry decision60days before expiry, using only a completed prior-hour close; execution starts the next hour over24hours. Exit is a24-hour schedule ending one hour before delivery. Do not substitute an assumed perfect settlement price. Per slice, both legs are capped at1%of prior24hour mean hourly notional volume. Initial40%capital budget per asset; rejected slots remain cash. No reallocation to the winning asset.',
'Always-on takes every scheduled contract. The fixed cost/cash gate requires observed basis above conservative four-leg base costs, cash opportunity cost and2%annual risk buffer. No estimated future funding is substituted into dated returns. At1Mcapital, the first development simulation could not unwind9ETHcontracts under its participation limit. That failure is retained. The100kproof-of-concept is the supported capacity claim.',
'', '## Perpetual mathematics and implementation',
'Buy spot and short exactly the same underlying quantity in a linear perpetual. Price P&L is q[(ST-S0)-(FT-F0)]; add actual funding q*mark*rate at each event and subtract costs. Spot and futures are marked separately. Futures unrealised profits are not bank cash. Reserve physical collateral for notional plus unrealised short losses; no interest on reserves. If cash is insufficient after a large price decline, realise futures gains through a paid close/reopen rather than creating free cash.',
'Compare always-on, conservative min(7day,30day)EWMA funding and pooledRidge(alpha10)forecasts. Ridge predicts next30daysfunding with quarterly trailing730daytraining, training-only standardisation and exclusion of every future label not completed at fit cutoff. Daily decisions use only available prior information and execute the next hour. Funding is credited to inventory held before the payment. Weekly integer-lot resizing and a high-gross-exposure resize are explicit.',
'Per asset, target20%NAVspot plus fully reserved margin. Entry compares30daypredictedfunding plusbasis with fees, two-capital-leg cash opportunity cost and2%annualbuffer. Three weak daily forecasts or adversebasis exit. No reverse carry requiring coin borrowing. Original2022validation selectedEWMA; execution and cash-proxy corrections were applied uniformly and the original choice was retained.',
'', '## Costs and robustness',
'All-in one-way base cost: spot12bp/futures7bp; moderate20/12; severe30/20. These are assumptions combining fees and adverse execution, not measured order-book spreads. Stress runs keep the original base-cost decision gate. Every open, resize, forced close and final liquidation is charged. Dated coin fees and extra spot needed to pay them are included.',
'| Design | Cost spot/futures bp | Total return | Cash total return | CAGR |', '|---|---:|---:|---:|---:|']
for table,model,name in [(crypto,'ewma_gate','Funding'),(dated[dated.period=='later'],'cost_cash_gate','Dated')]:
 for _,r in table[table.model==model].iterrows():
  fb=r.perp_bps if 'perp_bps' in r.index else r.future_bps
  lines.append(f'| {name} | {r.spot_bps:g}/{fb:g} | {P(r.total_return)} | {P(r.cash_return)} | {P(r.cagr)} |')
lines+=['','Asset-removal diagnostics retain original slot sizes; unused slots stay cash. Both BTC-only and ETH-only variants had positive excess return at base costs; no asset was reselected. Seeleave_one_asset_out.csv.','',
'## Inference and concentration','| Design | Block length | Annual arithmetic excess mean | 95% block-bootstrap interval | Long-run variance Sharpe | HAC mean p |','|---|---:|---:|---:|---:|---:|']
for file,name in [('crypto_locked_ewma_gate_cost12_7_hourly.csv','Funding'),('inverse_cost_cash_gate_cost12_7_hourly.csv','Dated')]:
 for d in D[file]['diagnostics']:
  lo,hi=d['bootstrap95_annual_mean'];lines.append(f"| {name} | {d['block_days']} | {P(d['annual_arithmetic_excess'])} | [{P(lo)}, {P(hi)}] | {d['long_run_variance_sharpe']:.2f} | {d['hac_mean_p_two_sided']:.3f} |")
lines += ['',f'The funding strategy has only{len(episodes)}holding episodes in the later period. The dated gate accepts{int(later_de.accepted.sum())}of{len(later_de)}later asset-expiry decisions; BTC/ETH episodes within a quarter are related, not independent trials. Standard daily Sharpe is not the headline evidence. Small samples, changing regimes and common exchange risk remain. Bootstrap/HAC summaries do not adjust for every discretionary research branch or model selection.',
'', '## Audit trail and limits',
'31meaningful tests passed.15final ledgers reconcile NAV, cash, inventory/unrealised P&L, order fees and information-before-execution.962retained source archives match download-manifestSHA256hashes. The pipeline retains raw inputs, exact sourceURLs, processed data and protocols.640monthlyperpetual/spot/funding files plus264datedmonthlyfiles and58dailyrepairs are included.',
'31spot-print hours per asset are unavailable over2020-Aug2026. A flagged prior spot/mark basis proxy values inventory only; it cannot fill orders. All missing dated mark/execution hours in the declared windows were recovered from official daily archives. A composite-index source was unavailable and was not treated as observed data.',
'USDfutures vsUSDTspot assumes parity. Free off-exchange cash earns the declared proxy; transfers and access to that cash return are not observed. Opening prices plus cost assumptions do not reconstruct executable bid/ask or legging risk. No actual historical order book, queue, ADL or exchange-default series is modelled. The margin stress checks are conditional OHLC diagnostics, not a universal liquidation guarantee. Taxes are excluded.',
'The later periods are chronological retrospective evaluations. Preliminary later results were seen before fixing an integer-lot execution bug and refining the cash proxy. This is disclosed; do not relabel them pristine unseen holdouts. Pre-correction summaries are retained as superseded audit history, never headline performance.',
'', '## What to do next',
'Freeze these rules and validate with recorded bid/ask and depth, actual fees, order-by-order fills, transfer delays and an independent forward paper ledger. Test a second venue without selecting it for historical returns. Record failed orders and quote-to-fill differences. Reassess expected excess return after custody, stablecoin, cash-access and operational haircuts. More ML or leverage is not the next priority.',
'', '## CV positioning',
'Use Cost-Aware Relative-Value Trading Research rather than claiming a novel arbitrage theorem or guaranteed trading income. Replace the old, unverified pairs-trading performance claims. Suggested bullets:',
'- Derived matched spot/inverse-futures hedges and tested44BTC/ETHquarterly contracts with coin fees, integer sizing and volume-limited execution.',
f'- A fixed cost-and-cash filter raised2023-Jun2026net return to{P(df.total_return)}from{P(db.total_return)}always-on, reducing trading costs by{100*(1-df.fees_paid/db.fees_paid):.0f}%.',
'- Built an audited hourly research engine with causal signals, collateral accounting, cost stresses and31tests; assessed performance using block bootstrap and HAC inference.',
'These are simulated results under declared assumptions. The strongest interview material is the economic mechanism, exact hedge, why the ETF idea failed, the capacity failure and the gap between daily Sharpe and dependence-aware evidence.',
'', '## Literature review','The separateLiterature_Review.mdprovides an access-aware review of11papers and links to original sources. Downloaded copyrighted paperPDFs are excluded from the deliverable archive.']
md=''.join(line+('\n' if line.startswith('|') and i+1<len(lines) and lines[i+1].startswith('|') else '\n\n')
           for i,line in enumerate(lines))
# Improve readability of compact drafting tokens used in protocol notes.
for a,b in [('seeleave','see leave'),('Seeleave','See leave'),('separateLiterature','separate Literature'),('mdprovides','md provides')]:md=md.replace(a,b)
(OUT/'Research_Report.md').write_text(tidy_text(md))

# PDF: fixed pages keep tables, captions and equations readable.
font=str(Path(matplotlib.get_data_path())/'fonts/ttf')+'/'
pdfmetrics.registerFont(TTFont('DV',font+'DejaVuSans.ttf'));pdfmetrics.registerFont(TTFont('DV-Bold',font+'DejaVuSans-Bold.ttf'))
styles=getSampleStyleSheet()
styles.add(ParagraphStyle('BodyX',fontName='DV',fontSize=10.2,leading=14.8,textColor=colors.HexColor('#243248'),spaceAfter=9))
styles.add(ParagraphStyle('TitleX',fontName='DV-Bold',fontSize=25,leading=30,textColor=colors.HexColor('#102c40'),spaceAfter=16))
styles.add(ParagraphStyle('H1X',fontName='DV-Bold',fontSize=18,leading=23,textColor=colors.HexColor('#102c40'),spaceAfter=14))
styles.add(ParagraphStyle('H2X',fontName='DV-Bold',fontSize=11.5,leading=16,textColor=colors.HexColor('#137a72'),spaceBefore=9,spaceAfter=6))
styles.add(ParagraphStyle('SmallX',fontName='DV',fontSize=8.5,leading=11.8,textColor=colors.HexColor('#566478'),spaceAfter=6))
styles.add(ParagraphStyle('CellX',fontName='DV',fontSize=8.7,leading=11.8,textColor=colors.HexColor('#243248')))
story=[]
def para(s,style='BodyX'):return Paragraph(s,styles[style])
def add(s,style='BodyX'):story.append(para(s,style))
def heading(s):add(s,'H2X')
def page(title):
 if story:story.append(PageBreak())
 add(title,'H1X')
def table(rows,widths):
 data=[[para(html.escape(str(c)),'CellX') for c in row] for row in rows]
 t=Table(data,colWidths=widths,hAlign='LEFT',repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#137a72')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dce2e8'))]))
 story.append(t);story.append(Spacer(1,10))
def footer(canvas,doc):
 canvas.setStrokeColor(colors.HexColor('#dce2e8'));canvas.line(44,41,551,41)
 canvas.setFont('DV',8);canvas.setFillColor(colors.HexColor('#66758a'));canvas.drawString(44,28,'FAKHRUDDIN HAKIM HUSSAIN  |  QUANT RESEARCH  |  25 OCT 2026');canvas.drawRightString(551,28,str(doc.page))

add('From pairs trading to<br/>cost-aware relative value','TitleX')
add('Literature review, mathematical design and audited backtests','H2X')
add('Prepared for Fakhruddin Hakim Hussain | 25 October 2026','SmallX')
add('The research now has a defensible economic mechanism and reproducible positive results under declared assumptions. The improvement comes from deciding when carry pays for capital and execution, rather than adding a more complex classifier.')
heading('What the evidence supports')
add('Keep the cost-aware carry engine as the strongest extension of the original project. Retire the old notebook\'s unverified performance claims. Treat the result as a research prototype: excess returns are modest and concentrated, and execution/counterparty risks remain outside the historical price ledger.')
heading('Funding carry | Jan 2023-Aug 2026')
table([['Model','Net total','Net CAGR','Daily excess SR'],['Always on',P(cb.total_return),P(cb.cagr),f'{cb.excess_sharpe:.2f}'],['EWMA gate',P(cf.total_return),P(cf.cagr),f'{cf.excess_sharpe:.2f}'],['Cash proxy',P(cf.cash_return),P(CASH(cf)),'-']],[164,107,107,129])
heading('Dated futures | Jan 2023-Jun 2026')
table([['Model','Net total','Net CAGR','Daily excess SR'],['Always on',P(db.total_return),P(db.cagr),f'{db.excess_sharpe:.2f}'],['Cost + cash gate',P(df.total_return),P(df.cagr),f'{df.excess_sharpe:.2f}'],['Cash proxy',P(df.cash_return),P(CASH(df)),'-']],[164,107,107,129])
add('All costs included. Cash proxy: lagged SOFR minus 25bp, floor zero. Total returns include cash interest. Different end dates mean these two experiments are not directly ranked. Read daily Sharpe with the dependence diagnostics in section 6.','SmallX')

page('1 | What changed in the equity idea')
heading('The original result was not an investable backtest')
add('The original notebook fitted PCA, clustering and pair tests across the same 2015-2019 history it traded. It then kept pairs that outperformed on that history. Signals and fills used the same close, while the ledger omitted daily unrealised risk, trading costs and short borrow. The fitted cointegrating spread was replaced by a ratio at the trading stage.')
add('Other audit findings: a list was modified during iteration; the notebook retained 39 winners while the README said 38; the reviewed code did not calculate the CV Sharpe of 1.09. The frozen equity universe, unclear corporate-action adjustments and absent borrow availability prevent a reliable overnight NSE-short claim.')
heading('A causal statistical-convergence pilot')
add('A fresh pilot used 16 economically related ETF pairs. Estimates used the prior 504 trading sessions and refitted quarterly. Trading used next-open prices, whole shares, cash distributions, borrow charges and a cash benchmark. It compared rolling spread signals, an OU cost gate and a partial-cointegration cost gate.')
add('The state-space model separated a temporary AR(1) deviation from a permanent random walk. Filtered states used only available observations; smoothed states were excluded from signals. The hedge fit was conditional, rather than the authors\' joint estimator.')
table([['Component','Research purpose'],['Temporary state M(t) = rho M(t-1) + noise','Estimate the displacement that may reverse.'],['Permanent state R(t) = R(t-1) + noise','Avoid assuming every shift must reverse.'],['Expected convergence versus costs','Require enough predicted return to pay for implementation.']],[214,293])
heading('Validation rejected this implementation')
add('All three ETF variants had negative net excess Sharpe in 2019-2021 at their base costs. The later ETF strategy test was left unopened. This is a useful negative result: statistical fit alone did not establish a tradable edge.')
add('The stronger question is therefore economic: what forces or pays for convergence? For spot-futures pairs, both legs reference the same asset. Funding and fixed maturity give measurable mechanisms that do not rely on two separate companies remaining economically similar.')

page('2 | Literature translated into decisions')
add('The review uses original papers, author implementations and official contract documentation. Access limitations are recorded rather than presenting every item as a full-paper review. The separate Markdown review gives the fuller synthesis.','SmallX')
rows=[['Source','Decision carried into this project']]
for author,insight,url,access in refs:rows.append([author,insight+' Access: '+access+'.'])
table(rows,[155,352])

page('3 | Dated futures: match the coin hedge')
heading('Research question')
add('Can a visible futures premium compensate for execution costs and the return available on cash, while the purchased coin itself collateralises the inverse short? This is a standard cash-and-carry mechanism; the research contribution is its tested accounting, execution and no-trade rule.')
heading('The mathematical identity')
add('Let C be dollar face, F0 the futures entry price, Ft the futures mark and St spot. A short inverse contract earns coin P&amp;L C(1/Ft - 1/F0). Buy net coin margin q = C/F0 after paying the entry coin fee.')
table([['Step','Identity before later fees'],['Coin equity','q + C(1/Ft - 1/F0) = C/Ft'],['Value in spot currency','Vt = C St/Ft'],['At ideal expiry convergence','If FT = ST, value becomes C.']],[190,317])
add('In the real test, exits occur before delivery at actual recorded prices. Residual basis is retained. Each entry slice is matched separately; partial closes release only matching collateral. Integer contract faces are USD 100 for BTC and USD 10 for ETH. Spot lots round to 0.001 coin; unsold dust remains marked inventory.')
heading('Fixed execution and selection rules')
add('Test all 44 BTC/ETH quarterly contracts from 2021Q1 through 2026Q2. Decide 60 days before expiry from a completed prior-hour close. Use 24 hourly entry slices and 24 exit slices ending one hour before delivery. Every slice is capped at 1% of prior 24-hour mean hourly notional volume on both legs.')
add('Allocate a 40% cash budget per asset. The gate requires the prior observed premium to exceed four-leg base costs, cash opportunity cost and a 2% annual risk buffer. Rejected slots stay cash. No horizon, asset or threshold was optimised on later returns.')
heading('A real capacity limit')
add('The first USD 1 million development simulation failed its scheduled unwind by 9 ETH contracts (USD 90 face). That failure is retained. The supported implementation is a USD 100,000 proof-of-concept, under the same dates, thresholds and participation limits. It does not establish million-dollar capacity.')

page('4 | Funding: forecast cash flow, reserve capital')
heading('The matched linear hedge')
add('Buy q units of spot and short exactly q units of a linear perpetual. Price P&amp;L is q[(ST - S0) - (FT - F0)]. Add observed funding q x settlement mark x funding rate and subtract both-leg costs. Funding is paid only on inventory held before the event; the current payment cannot be used to enter and earn itself.')
heading('Three declared models')
table([['Model','Rule'],['Always on','Continuously hold the matched spot/short hedge.'],['EWMA gate','Conservative minimum of past 7-day and 30-day funding estimates.'],['Ridge gate','Forecast next 30-day funding using lagged funding, basis, returns and volatility; alpha = 10.']],[140,367])
add('Ridge uses quarterly trailing 730-day training, training-only standardisation and a 30-day label purge. Every training target must end before the fit date. Daily decisions use completed information and execute one hour later. A three-day weak-funding rule, adverse-basis exit and weekly integer-lot resizing are explicit.')
heading('Collateral is not free')
add('Target 20% NAV spot per asset plus fully reserved short margin. Keep futures unrealised P&amp;L separate from physical cash. Reserve extra cash for unrealised short losses; posted reserves earn no interest. If falling spot leaves cash short despite offsetting futures gains, realise those gains through a paid futures close/reopen. No synthetic free cash is created.')
heading('Selection and research history')
add('Original 2022 validation selected EWMA. After later preliminary results were seen, an exit-dust execution bug and the coarse cash proxy were corrected uniformly. The original selection was retained. These are audit-corrected retrospective chronological results, not a pristine unseen holdout.')
add(f'The final later-period funding result has {len(episodes)} holding episodes. Both single-asset removal checks retain positive base-cost excess return, with unused slots held in cash. No winning asset is reselected from those diagnostics.')

page('5 | Returns after execution and cash costs')
story.append(Image(str(OUT/'cumulative_returns.png'),width=507,height=400))
heading('Cost sensitivity: spot / futures, one-way bp')
rows=[['Design','Cost bp','Net total','Cash total']]
for tab,model,name in [(crypto,'ewma_gate','Funding'),(dated[dated.period=='later'],'cost_cash_gate','Dated')]:
 for _,r in tab[tab.model==model].iterrows():
  fb=r.perp_bps if 'perp_bps' in r.index else r.future_bps
  rows.append([name,f'{r.spot_bps:g}/{fb:g}',P(r.total_return),P(r.cash_return)])
table(rows,[130,110,133,134])
add('Costs combine fees and adverse execution. They are not measured historical bid/ask spreads. The base-cost entry hurdle stays unchanged in stress runs. Severe costs leave very little dated-futures excess return; a favourable base case is not a universal profitability claim.','SmallX')

page('6 | Uncertainty and economic significance')
story.append(Image(str(OUT/'uncertainty.png'),width=507,height=169))
rows=[['Design / block','Annual excess mean','95% interval','LRV Sharpe']]
for file,name in [('crypto_locked_ewma_gate_cost12_7_hourly.csv','Funding'),('inverse_cost_cash_gate_cost12_7_hourly.csv','Dated')]:
 for q in D[file]['diagnostics']:
  lo,hi=q['bootstrap95_annual_mean'];rows.append([f"{name} / {q['block_days']}d",P(q['annual_arithmetic_excess']),f'[{P(lo)}, {P(hi)}]',f"{q['long_run_variance_sharpe']:.2f}"])
table(rows,[130,120,157,100])
add('LRV uses Bartlett HAC long-run variance at 30/90 daily lags. Intervals use 2,000 circular-block bootstrap samples. These diagnostics preserve some serial dependence; they do not create independent trades, remove all research-selection bias or price exchange-default risk.','SmallX')
heading('Where the money came from')
cpnl=ch.nav.iloc[-1]-1e6;basis=cpnl-ch.funding.sum()-ch.interest.sum()+ch.fees.sum()
add(f'Funding gate: {F(cpnl)} USDT total P&amp;L = {F(ch.funding.sum())} funding + {F(ch.interest.sum())} cash interest + {F(basis)} basis/execution P&amp;L - {F(ch.fees.sum())} costs. Most of the headline return is cash interest. Excess final wealth versus the cash proxy is {F(1e6*(cf.total_return-cf.cash_return))} USDT.')
add(f'The dated gate accepted {int(later_de.accepted.sum())} of {len(later_de)} later asset-expiry decisions. The BTC and ETH positions in the same quarter are related observations. Later daily max drawdown is {P(df.max_drawdown_daily)}, while the full 2021-onward path includes the larger 2021 basis-widening drawdown (about 2.65%).')
heading('Unpriced loss can overwhelm the edge')
peak=float((ch.spot_value+ch.posted_collateral+ch.futures_unrealized).max())
add(f'A hypothetical 2% loss on the funding strategy\'s peak exchange receivable is about {F(.02*peak)} USDT, compared with {F(1e6*(cf.total_return-cf.cash_return))} excess final wealth. This is a loss scenario, not an estimated default probability. A smooth price ledger is not a complete risk model.')

page('7 | Data integrity and reproducibility')
heading('What has been verified')
add('31 meaningful tests passed: hedge identities, funding ownership/timing, cash and coin fee accounting, partial unwinds, integer-lot exits, label purging, future-data invariance, unavailable bars and publication-lag/day-count handling. All 15 final ledgers reconcile NAV, order fees and information-before-execution. No declared hourly margin-stress breach occurred.')
add('962 source archives match their retained download hashes: 640 monthly spot/perpetual/funding archives, 264 dated-futures monthly archives and 58 daily repairs. The package includes raw data, processed inputs, source URLs, protocols, fit logs, final ledgers and tests. Downloaded copyrighted research-paper PDFs are excluded.')
heading('Data limitations that remain')
add('There are 31 unavailable spot-print hours per asset over 2020-Aug 2026. A flagged previous spot/mark basis proxy is used only to value inventory and cannot fill an order. Dated-contract gaps were recovered from official daily archives. A missing composite-index source was not substituted as observed data.')
add('The USD futures / USDT spot comparison assumes parity. Cash interest is an assumed off-exchange SOFR-minus-25bp proxy with a seven-day information lag, not an investable fund total-return series. Transfers, historical depth, queues, asynchronous legs, ADL, taxes and exchange failures are not reconstructed. Hourly OHLC stress is conditional evidence, not a general liquidation guarantee.')
heading('Reproduce from the included snapshot')
for s in ['Install the pinned requirements in a fresh Python environment.','Run python -m pytest -q tests.','Run carry.py --phase development and carry.py --phase locked. The latter checks the frozen code/protocol hashes.','Run inverse.py, robustness.py and diagnostics.py. Read the final summaries rather than superseded audit folders.']:
 add('• '+s)
heading('The next experiment')
add('Freeze these rules and record forward bid/ask, available depth, actual fees, quote-to-fill slippage, rejected orders and transfer timing. Keep an independent paper ledger and test a second venue without choosing it for historical returns. Better execution evidence and more independent opportunities take priority over more ML or leverage.')

page('8 | Turning the work into a quant CV project')
heading('Suggested title')
add('Cost-Aware Relative-Value Trading Research')
heading('Evidence-backed bullets')
for s in [
'Derived matched spot/inverse-futures hedges and tested 44 BTC/ETH quarterly contracts with coin fees, integer sizing and volume-limited execution.',
f'A fixed cost-and-cash filter raised 2023-Jun 2026 net return to {P(df.total_return)} from {P(db.total_return)} always-on, reducing trading costs by {100*(1-df.fees_paid/db.fees_paid):.0f}%.',
'Built an audited hourly research engine with causal signals, collateral accounting, cost stresses and 31 tests; assessed results using block bootstrap and HAC inference.']:
 add('• '+s)
heading('Recruiter and technical-review assessment')
table([['Dimension','Assessment'],['Research question','Clear economic mechanism, rather than a generic clustering exercise.'],['Mathematics','Exact inverse-contract hedge, state-space comparison and explicit capital accounting.'],['Engineering','Reproducible public-data pipeline, source integrity, event-time ledgers and meaningful tests.'],['Empirical result','Positive under stated assumptions; modest excess and limited independent episodes.'],['Novelty','A careful implementation and comparison of known mechanisms, not a new arbitrage theorem.']],[140,367])
add('This is stronger than the old project because its numbers can be traced to cash flows and its failure cases are documented. Do not advertise a guaranteed strategy, a novel pricing result, million-dollar capacity, or the unadjusted funding Sharpe as the main achievement.')
add('Before an interview, be able to derive the coin hedge, explain why the ETF version failed, reproduce one trade by hand, reconcile fees and collateral, and explain why cash, capacity and dependence change the result.')

page('References and primary data sources')
for i,(author,insight,url,access) in enumerate(refs,1):
 add(f'<b>{i}. {html.escape(author)}</b> <link href="{html.escape(url,quote=True)}" color="#137a72">Original source</link>. Access: {html.escape(access)}.','SmallX')
heading('Contract and data documentation')
for title,url in [
('Official Binance public archive documentation','https://github.com/binance/binance-public-data'),
('Coin-margined contract faces and collateral','https://www.binance.com/en/support/faq/detail/85eac2bba0b342819122dc9bd4745e9b'),
('Inverse-contract P&L formulas','https://www.binance.com/en/support/faq/detail/3a55a23768cb416fb404f06ffedde4b2'),
('Quarterly delivery and settlement convention','https://www.binance.com/en-BH/support/faq/detail/a3401595e1734084959c61491bc0dbe3'),
('NYFed SOFR definition and publication','https://www.newyorkfed.org/markets/reference-rates/sofr'),
('Kenneth French factor data (ETF pilot)','https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html')]:
 add(f'<link href="{html.escape(url,quote=True)}" color="#137a72">{html.escape(title)}</link>','SmallX')
heading('Interpretation boundary')
add('Literature motivates the hypotheses; it does not validate this implementation. All performance numbers in this report come from the accompanying code and input snapshot, not from published paper returns. Source-access levels are recorded in the separate review. The study includes unsuccessful branches and post-observation corrections so that later readers can assess research selection honestly.')

SimpleDocTemplate(str(OUT/'Quant_Relative_Value_Research.pdf'),pagesize=(595.276,841.89),rightMargin=44,leftMargin=44,topMargin=44,bottomMargin=54,title='Cost-Aware Relative-Value Trading Research',author='Fakhruddin Hakim Hussain').build(story,onFirstPage=footer,onLaterPages=footer)
# Compact final comparison for external reuse.
final=pd.concat([crypto.assign(design='funding'),dated[dated.period=='later'].assign(design='dated')],ignore_index=True)
final.to_csv(OUT/'Final_Results.csv',index=False)
print('Built',OUT/'Quant_Relative_Value_Research.pdf')
