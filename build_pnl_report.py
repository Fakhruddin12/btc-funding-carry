from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter,StrMethodFormatter
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.colors import HexColor,white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'/'pnl';REPORT=ROOT/'output'/'pdf';REPORT.mkdir(parents=True,exist_ok=True)
TAGS=['development','validation_2025']
labels=['Development: Jan 2022 - Dec 2024','Later test: Feb - Dec 2025']
stats={tag:json.loads((OUT/tag/'summary.json').read_text())['scenarios'] for tag in TAGS}
for tag in TAGS:
    directory=OUT/tag
    for mult in [1,2]:
        d=pd.read_csv(directory/f'daily_{mult}x.csv')
        cumulative=['spot_pnl','perp_mark_pnl','execution_basis_pnl','funding','spot_fee','perp_fee','spot_slippage','perp_slippage']
        statement=d[['timestamp','equity','cash','quantity','spot_value','perp_unrealized','futures_equity','drawdown']].copy()
        statement['opening_equity']=d.equity.shift(1).fillna(10000)
        for k in cumulative:statement[k]=d[k].diff().fillna(d[k].iloc[0])
        statement['basis_pnl']=statement.spot_pnl+statement.perp_mark_pnl+statement.execution_basis_pnl
        statement['fees']=statement.spot_fee+statement.perp_fee
        statement['slippage']=statement.spot_slippage+statement.perp_slippage
        statement['net_pnl']=statement.funding+statement.basis_pnl-statement.fees-statement.slippage
        assert np.allclose(statement.net_pnl,statement.equity-statement.opening_equity,atol=1e-7)
        statement['interval_start']=d.timestamp.shift(1).fillna(d.timestamp.iloc[0])
        statement['interval_hours']=(pd.to_datetime(statement.timestamp)-pd.to_datetime(statement.interval_start)).dt.total_seconds()/3600
        statement.to_csv(directory/f'daily_statement_{mult}x.csv',index=False)

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(2,2,figsize=(11,7),gridspec_kw={'height_ratios':[2.3,1]},layout='constrained')
for j,tag in enumerate(TAGS):
    d=pd.read_csv(OUT/tag/'daily_1x.csv');x=pd.to_datetime(d.timestamp,utc=True)
    ds=pd.read_csv(OUT/tag/'daily_2x.csv')
    elapsed=(x-x.iloc[0]).dt.total_seconds()/86400
    axs[0,j].plot(x,d.equity-10000,color='#174D72',lw=1.8,label='Net carry P&L')
    axs[0,j].plot(x,ds.equity-10000,color='#D38932',lw=1.2,label='Doubled costs')
    axs[0,j].plot(x,10000*(1.05**(elapsed/365.25)-1),color='#66717A',ls='--',lw=1.2,label='5% cash hurdle scenario')
    axs[0,j].set_title(labels[j],loc='left',fontsize=11,fontweight='bold')
    axs[0,j].set_ylabel('Cumulative P&L (USDT)')
    axs[0,j].yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    axs[0,j].grid(axis='y',alpha=.2);axs[0,j].legend(loc='upper left',fontsize=8,frameon=False)
    axs[1,j].fill_between(x,d.drawdown*100,0,color='#174D72',alpha=.2)
    axs[1,j].plot(x,d.drawdown*100,color='#174D72',lw=1)
    axs[1,j].set_ylabel('Drawdown (%)');axs[1,j].grid(axis='y',alpha=.2)
    for a in axs[:,j]:a.tick_params(axis='x',rotation=25,labelsize=8)
fig.suptitle('BTC funding carry | cash ledger, 10,000 USDT per test',fontsize=14,fontweight='bold')
fig.savefig(OUT/'equity_drawdown.png',dpi=180);plt.close(fig)

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleBlue',fontName='Helvetica-Bold',fontSize=22,leading=26,textColor=HexColor('#173E58'),spaceAfter=12))
styles.add(ParagraphStyle(name='SubBlue',fontName='Helvetica-Bold',fontSize=12,leading=16,textColor=HexColor('#173E58'),spaceBefore=12,spaceAfter=7))
styles.add(ParagraphStyle(name='BodySmall',fontName='Helvetica',fontSize=9,leading=13,spaceAfter=8))
styles.add(ParagraphStyle(name='TinyNote',fontName='Helvetica',fontSize=8,leading=11,textColor=HexColor('#52606D'),spaceAfter=7))
P=lambda text:Paragraph(text,styles['BodySmall'])
H=lambda text:Paragraph(text,styles['SubBlue'])
money=lambda n:f'{n:,.2f}'
pct=lambda n:f'{n:.2%}'
def table(rows,widths):
    t=Table(rows,colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#173E58')),('TEXTCOLOR',(0,0),(-1,0),white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[HexColor('#F1F5F8'),white]),('ALIGN',(1,1),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,-1),(-1,-1),.5,HexColor('#CDD7DF'))]))
    return t
s=[stats[t]['1'] for t in TAGS]
flow=[Paragraph('BTC funding carry: P&L report',styles['TitleBlue']),Paragraph('Historical simulation | 10,000 USDT initial capital | prepared 16 October 2026',styles['TinyNote']),P('A fully funded BTC spot holding is hedged by an equal-quantity short linear perpetual. Funding is collected or paid while positions remain open. Monthly rebalances trade only the change in BTC quantity. Every test ends with both positions closed. This is a price-proxy backtest, not live or order-book-verified performance.'),H('Account-level profit and loss')]
rows=[['USDT unless stated','2022-2024 development','Feb-Dec 2025 later test']]
for name,fn in [
('Initial capital',lambda x:money(x['initial_capital'])),('Funding income',lambda x:money(x['funding'])),('Basis P&L',lambda x:money(x['basis_pnl'])),('Trading fees',lambda x:'-'+money(x['spot_fees']+x['perp_fees'])),('Assumed slippage',lambda x:'-'+money(x['spot_slippage']+x['perp_slippage'])),('Net P&L',lambda x:money(x['net_pnl'])),('Final cash, positions closed',lambda x:money(x['final_equity'])),('Total return',lambda x:pct(x['total_return'])),('Maximum daily drawdown',lambda x:pct(x['max_daily_drawdown']))]:rows.append([name,*[fn(x) for x in s]])
flow +=[table(rows,[185,157,157]),H('Calendar-year attribution'),P('Returns below use the running account balance. The later test starts from a separate 10,000 USDT account and covers 11 months. Terminal January 1 funding and final close costs are included in the concluding December period.')]
annual=[['Period','Net P&L (USDT)','Return on capital']]
for tag in TAGS:
    a=pd.read_csv(OUT/tag/'annual_1x.csv')
    for _,r in a.iterrows():annual.append([str(int(r.year))+(' (Feb-Dec)' if tag=='validation_2025' else ''),money(r.net_pnl),pct(r.return_on_capital)])
flow +=[table(annual,[185,157,157]),Spacer(1,10),P('Positive nominal P&L is not sufficient evidence of an attractive investment. Compare each test with the capital hurdle and account for unmodeled venue and stablecoin risks. No predictive entry signal has been fitted.')]
flow +=[PageBreak(),Paragraph('Equity, drawdown and cost stress',styles['TitleBlue']),Image(str(OUT/'equity_drawdown.png'),width=499,height=318),Spacer(1,10)]
stress=[['Scenario / comparison','Development','Later test']]
for name,fn in [('Base-cost net P&L',lambda tag:money(stats[tag]['1']['net_pnl'])),('Doubled-cost net P&L',lambda tag:money(stats[tag]['2']['net_pnl'])),('5% cash hurdle: terminal value',lambda tag:money(stats[tag]['1']['cash_hurdle_terminal'])),('Strategy minus cash hurdle',lambda tag:money(stats[tag]['1']['final_equity']-stats[tag]['1']['cash_hurdle_terminal'])),('Worst valuation-interval P&L',lambda tag:money(stats[tag]['1']['worst_daily_pnl'])),('Minimum futures cash balance',lambda tag:money(stats[tag]['1']['minimum_cash'])),('Minimum stressed margin buffer',lambda tag:money(stats[tag]['1']['minimum_margin_stress_buffer']))]:stress.append([name,*[fn(t) for t in TAGS]])
flow +=[table(stress,[225,137,137]),Spacer(1,10),P('The cash hurdle is an illustrative 5% annual compounding scenario with the same starting capital and elapsed time. It is not an audited historical investment or an assumed return on collateral. The strategy earns no collateral interest in this simulation.'),P('Drawdown is measured at observed midnight valuations plus entry and final-close endpoints. Small measured drawdowns do not include exchange failure, stablecoin depegging, liquidation gaps or inability to trade during outages. The chart is not a forecast.')]
flow +=[PageBreak(),Paragraph('Ledger, validation and limits',styles['TitleBlue']),H('Cash and valuation identity'),P('Equity = USDT cash + BTC quantity x spot price + short BTC quantity x (average perpetual entry price - mark price). The ledger tracks perpetual entry averages, partial-close realized P&L, funding cash flows and each cost debit. Final positions are zero, so terminal equity is cash.'),P('P&L = funding + spot price P&L + perpetual price P&L + the execution-price/mark adjustment - spot fees - perpetual fees - slippage. Every hourly observation reconciles this attribution to account equity within 0.000001 USDT.'),H('Trading and risk assumptions'),P('At 01:00 UTC on each first day of the month, target roughly half the account in BTC spot and retain the rest as futures collateral. Both legs have the same quantity, rounded down to a 0.001 BTC research lot. This lot is a modeling restriction, not a reconstruction of every historical exchange order filter. Spot fee: 10 basis points per execution. Perpetual fee: 5 basis points. Additional slippage: 2 basis points per leg per execution. Stress doubles all four cost coefficients.'),P('All USDT not invested in spot is assigned to futures collateral during holding periods. Monthly spot funding uses actual available cash; no borrowing against unrealized profit is required. Initial margin is checked against a 50% notional scenario. Maintenance stress uses 1% of notional at the hourly mark high, debits negative funding within the hour and does not credit positive funding early. Any breach causes the replay to fail rather than report a completed profit.'),H('Historical validation and checks'),P('The 2022-2024 fractional-quantity cash ledger reproduces the earlier terminal result within 0.000001 USDT. The primary report adds lot rounding. Strategy, sizing, cost and margin rules were recorded before downloading February 2025 onward data. January 2025 was already downloaded and is excluded from the later test. A report-only annual grouping fix is documented; no positions or strategy rules changed after freezing.'),P('Eight accounting tests pass, covering directional cancellation, funding booking time, partial-close realization, lot sizing, fee debits, collateral allocation and avoiding redundant round trips. These verify accounting, not profitability. Later-period performance is a single historical validation, not a broad statistical proof.'),H('Data and practical limitations'),P('Official Binance monthly spot, perpetual, mark-price and funding archives are used. Source URLs and hashes are retained. Three missing development mark days were restored from official daily archives. One development spot hour has a stale valuation, explicitly flagged; no entry, exit or daily report mark uses a stale price. Funding uses native settlement timestamps and scheduled-hour mark opens as settlement-price proxies. Execution uses hourly trade-price opens plus assumed costs.'),P('Bid/ask depth, legging risk, actual historical fee tiers and margin rules, sub-hour liquidation paths, operational transfers, venue solvency, stablecoin dollar value and taxes are not reconstructed. Archive event time and completeness do not prove historical data publication availability. Continuous equal-quantity hedging removes the main BTC direction exposure but leaves funding and basis risk.'),H('Reproduce and inspect'),P('See daily_statement_1x.csv for interval-level P&L; trades_1x.csv for execution and realized futures P&L; funding_1x.csv for every payment; hourly_1x.csv.gz for marked positions, cash and margin checks. Run pnl.py for development and pnl.py --validation for the later test. PNL_PROTOCOL.json records frozen choices. Source archives and manifests are included.'),Paragraph('Primary references: github.com/binance/binance-public-data; binance.com/en/support/faq/detail/360033525031. Economic background: Schmeling, Schrimpf and Todorov, Crypto Carry, BIS Working Paper 1087 (2023).',styles['TinyNote'])]
def footer(c,doc):
    c.setStrokeColor(HexColor('#D4DDE4'));c.line(48,39,547,39)
    c.setFont('Helvetica',8);c.setFillColor(HexColor('#52606D'));c.drawString(48,27,'RESEARCH SIMULATION | USDT-denominated | no live trading')
    c.drawRightString(547,27,str(doc.page))
path=REPORT/'Funding_carry_PnL_report.pdf'
doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=42,bottomMargin=50)
from kpi_report_appendix import appendix
flow += appendix(ROOT,styles,table)
doc.build(flow,onFirstPage=footer,onLaterPages=footer)
print(path)
