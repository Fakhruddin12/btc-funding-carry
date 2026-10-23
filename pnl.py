"""Self-financing spot/linear-perpetual carry ledger. All currency amounts in USDT."""
from pathlib import Path
import json,hashlib,datetime
import pandas as pd
import numpy as np
from study import load,repair_mark
ROOT=Path(__file__).resolve().parent

def target_quantity(equity,old,s,p,multiple=1,lot=.001):
    k=multiple*(.0012*s+.0007*p)
    q=(equity+k*old)/(2*s+k) if equity/(2*s)>=old else (equity-k*old)/(2*s-k)
    return np.floor((q+1e-12)/lot)*lot if lot else q

def sources(start,end):
    months=pd.date_range(start,end,freq='MS').strftime('%Y-%m').tolist()
    data={k:load(k,months) for k in ['spot','perp','mark','funding']}
    first=pd.Timestamp(start,tz='UTC')+pd.Timedelta(hours=1)
    last=pd.Timestamp(end,tz='UTC')+pd.Timedelta(hours=1)
    hours=pd.date_range(first,last,freq='h')
    data['mark'],repairs=repair_mark(data['mark'],hours,write_manifest=False)
    assert len(hours.difference(data['mark'].index))==0
    f=data['funding'];scheduled=f.index.floor('8h')
    assert not scheduled.has_duplicates
    assert (f.index-scheduled).total_seconds().max()<1
    expected=pd.date_range(first.ceil('8h'),last.floor('8h'),freq='8h')
    assert len(expected.difference(scheduled))==0
    assert f.funding_interval_hours.eq(8).all()
    f=f.copy();f['scheduled_time']=scheduled
    f=f.join(data['mark']['open'].rename('funding_mark_proxy'),on='scheduled_time')
    f=f.loc[(f.index>first)&(f.index<last)]
    assert f.funding_mark_proxy.notna().all()
    f['per_btc']=f.rate*f.funding_mark_proxy
    data['funding']=f
    return data,hours,repairs

def replay(data,hours,multiple=1,lot=.001,initial=10000):
    spot=data['spot'];perp=data['perp'];marks=data['mark'];fund=data['funding']
    cash=initial;q=0.;avg=0.;last_s=None;last_m=None;prior=hours[0]
    rows=[];events=[];fundrows=[]
    cum={k:0. for k in ['spot_pnl','perp_mark_pnl','execution_basis_pnl','funding','spot_fee','perp_fee','spot_slippage','perp_slippage','realized_perp']}
    for t in hours:
        oldq=q
        # Real native funding timestamps determine cash booking. Positions do not
        # change inside these hourly intervals; decisions occur at 01:00 UTC only.
        due=fund.loc[(fund.index>prior)&(fund.index<=t)]
        income=float(due.per_btc.sum()*q);cash+=income;cum['funding']+=income
        for ft,fr in due.iterrows():fundrows.append(dict(timestamp=str(ft),scheduled_time=str(fr.scheduled_time),quantity=q,rate=fr.rate,mark_proxy=fr.funding_mark_proxy,cashflow=q*fr.per_btc))
        si=spot.index.searchsorted(t,side='right')-1
        st=spot.index[si];s=float(spot.iloc[si].open)
        stale=(t-st).total_seconds()/3600
        assert stale<=1,(t,st)
        m=float(marks.loc[t,'open'])
        pnl_s=0 if last_s is None else q*(s-last_s)
        pnl_p=0 if last_m is None else q*(last_m-m)
        cum['spot_pnl']+=pnl_s;cum['perp_mark_pnl']+=pnl_p
        sf=pf=ss=ps=realized=execution=0.
        trade=(t.day==1 and t.hour==1) or t==hours[-1]
        if trade:
            assert st==t and t in perp.index  # no stale execution prices allowed
            p=float(perp.loc[t,'open'])
            equity_trade=cash+q*s+q*(avg-p)
            newq=0. if t==hours[-1] else target_quantity(equity_trade,q,s,p,multiple,lot)
            assert newq>=0
            dq=newq-q
            sf=multiple*.001*abs(dq)*s;pf=multiple*.0005*abs(dq)*p
            ss=multiple*.0002*abs(dq)*s;ps=multiple*.0002*abs(dq)*p
            if dq<0:realized=(-dq)*(avg-p);cash+=realized
            if dq>0:avg=(q*avg+dq*p)/newq
            cash-=dq*s+sf+pf+ss+ps
            execution=dq*(p-m)
            q=newq
            if q==0:avg=0.
            assert cash>=-1e-8,('cash borrowing required',t,cash)
            # 2x exchange leverage configuration (50% initial margin), with much
            # more cash/equity normally reserved. Historical filters not reconstructed.
            assert cash+q*(avg-m)>=.5*q*m-1e-8,('initial margin fails',t)
            events.append(dict(timestamp=str(t),old_quantity=oldq,new_quantity=q,quantity_change=dq,spot_reference=s,perp_reference=p,mark=m,spot_cashflow=-dq*s,realized_perp=realized,spot_fee=sf,perp_fee=pf,spot_slippage=ss,perp_slippage=ps,cash_after=cash,spot_market_value=q*s,perp_unrealized=q*(avg-m),equity_mark=cash+q*s+q*(avg-m),equity_execution_reference=cash+q*s+q*(avg-p)))
        for k,v in dict(execution_basis_pnl=execution,spot_fee=sf,perp_fee=pf,spot_slippage=ss,perp_slippage=ps,realized_perp=realized).items():cum[k]+=v
        futures_equity=cash+q*(avg-m)
        nav=futures_equity+q*s
        costs=cum['spot_fee']+cum['perp_fee']+cum['spot_slippage']+cum['perp_slippage']
        attribution=cum['spot_pnl']+cum['perp_mark_pnl']+cum['execution_basis_pnl']+cum['funding']-costs
        assert abs(nav-initial-attribution)<1e-6,(t,nav-initial-attribution)
        # Adverse intra-hour stress: high mark and all negative funding in bar,
        # no positive funding credit before receipt. Used for risk audit only.
        if t<hours[-1]:
            high=float(marks.loc[t,'high'])
            nextfund=fund.loc[(fund.index>t)&(fund.index<t+pd.Timedelta(hours=1))]
            negative=float(nextfund.per_btc.clip(upper=0).sum()*q)
            min_equity=cash+q*(avg-high)+negative
            maintenance=.01*q*high
            buffer=min_equity-maintenance
            utilization=maintenance/min_equity if min_equity>0 else np.inf
        else:buffer=futures_equity;utilization=0.
        assert buffer>0,('margin proxy breach: stop, do not claim closed P&L',t,buffer)
        row=dict(timestamp=str(t),quantity=q,spot_source_time=str(st),spot_stale_hours=stale,spot=s,mark=m,cash=cash,perp_entry_average=avg,spot_value=q*s,perp_unrealized=q*(avg-m),futures_equity=futures_equity,equity=nav,margin_stress_buffer=buffer,maintenance_utilization_stress=utilization,**cum)
        rows.append(row);last_s=s;last_m=m;prior=t
    hourly=pd.DataFrame(rows);trades=pd.DataFrame(events);payments=pd.DataFrame(fundrows)
    assert abs(q)<1e-12 and abs(cash-hourly.equity.iloc[-1])<1e-8
    assert len(payments)==len(fund)
    return hourly,trades,payments

def summarize(h,trades,initial=10000):
    h=h.copy();h.index=pd.to_datetime(h.timestamp,utc=True)
    # Midnight marks plus exact initial/final endpoints; no carried spot at these marks.
    d=h.loc[(h.index.hour==0)|h.index.isin([h.index[0],h.index[-1]])].copy()
    assert d.spot_stale_hours.eq(0).all()
    d['pnl']=d.equity.diff();d.loc[d.index[0],'pnl']=d.equity.iloc[0]-initial
    d['return']=d.equity.pct_change();d.loc[d.index[0],'return']=d.equity.iloc[0]/initial-1
    d['drawdown']=d.equity/np.maximum.accumulate(np.r_[initial,d.equity.to_numpy()])[1:]-1
    period=[];prev=initial
    # Last observation BEFORE next year's first rebalance, matching cash attribution
    # across observed calendar timestamps. The terminal Jan-1 close belongs to Dec.
    h['accounting_year']=h.index.year
    h.loc[h.index.normalize()==h.index[-1].normalize(),'accounting_year']=(h.index[-1]-pd.Timedelta(hours=2)).year
    cumulative_keys=['spot_pnl','perp_mark_pnl','execution_basis_pnl','funding','spot_fee','perp_fee','spot_slippage','perp_slippage']
    lastcum={k:0. for k in cumulative_keys}
    for year,g in h.groupby('accounting_year',sort=True):
        end=g.iloc[-1];r=dict(year=int(year),starting_equity=prev,ending_equity=float(end.equity),net_pnl=float(end.equity-prev),return_on_capital=float(end.equity/prev-1))
        for k in cumulative_keys:r[k]=float(end[k]-lastcum[k]);lastcum[k]=end[k]
        r['basis_pnl']=r['spot_pnl']+r['perp_mark_pnl']+r['execution_basis_pnl']
        r['fees']=r['spot_fee']+r['perp_fee'];r['slippage']=r['spot_slippage']+r['perp_slippage']
        period.append(r);prev=float(end.equity)
    final=h.iloc[-1]
    elapsed=(h.index[-1]-h.index[0]).total_seconds()/86400
    summary=dict(initial_capital=initial,final_equity=float(final.equity),net_pnl=float(final.equity-initial),total_return=float(final.equity/initial-1),cagr=float((final.equity/initial)**(365.25/elapsed)-1),funding=float(final.funding),basis_pnl=float(final.spot_pnl+final.perp_mark_pnl+final.execution_basis_pnl),spot_fees=float(final.spot_fee),perp_fees=float(final.perp_fee),spot_slippage=float(final.spot_slippage),perp_slippage=float(final.perp_slippage),max_daily_drawdown=float(d.drawdown.min()),worst_daily_pnl=float(d.pnl.min()),best_daily_pnl=float(d.pnl.max()),positive_daily_observations=int((d.pnl>0).sum()),daily_observations=len(d),stale_spot_hour_count=int((h.spot_stale_hours>0).sum()),funding_receipts_included=True,minimum_cash=float(h.cash.min()),minimum_margin_stress_buffer=float(h.margin_stress_buffer.min()),maximum_maintenance_utilization=float(h.maintenance_utilization_stress.max()),cash_hurdle_terminal=initial*1.05**(elapsed/365.25),rebalance_events=len(trades)-1)
    return d,pd.DataFrame(period),summary

def run(start,end,tag):
    data,hours,repairs=sources(start,end)
    out=ROOT/'results'/'pnl'/tag;out.mkdir(parents=True,exist_ok=True)
    summaries={}
    for multiplier in [1,2]:
        h,t,f=replay(data,hours,multiple=multiplier)
        d,a,s=summarize(h,t);summaries[str(multiplier)]=s
        h.to_csv(out/f'hourly_{multiplier}x.csv.gz',index=False)
        d.to_csv(out/f'daily_{multiplier}x.csv',index=False)
        a.to_csv(out/f'annual_{multiplier}x.csv',index=False)
        t.to_csv(out/f'trades_{multiplier}x.csv',index=False)
        f.to_csv(out/f'funding_{multiplier}x.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(start=start,end=end,repairs=repairs,scenarios=summaries),indent=2))
    print(tag,json.dumps(summaries,indent=2),flush=True)
    return data,hours

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--validation',action='store_true');a=p.parse_args()
    if a.validation:run('2025-02-01','2026-01-01','validation_2025')
    else:
        data,hours=run('2022-01-01','2025-01-01','development')
        # Exact reconciliation to previous fractional-quantity, monthly ledger.
        h,t,f=replay(data,hours,lot=0)
        old=pd.read_csv(ROOT/'results'/'continuous_cost_1x.csv')
        assert abs(h.equity.iloc[-1]-old.wealth_end.iloc[-1])<1e-6
        print('Fractional ledger reconciles to previous result within 1e-6 USDT.',flush=True)
