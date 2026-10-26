"""Dated inverse-futures convergence research; cash/coin double-entry ledger."""
from pathlib import Path
import argparse,json,hashlib,math
import numpy as np
import pandas as pd
from carry import cash_rates,metrics
from inverse_download import contracts
from io_utils import save_frame
ROOT=Path(__file__).parent
STEP={'BTC':.001,'ETH':.001}


def load():
    spots={a:pd.read_csv(ROOT/'crypto_data'/f'{a}USDT_spot.csv',index_col=0,parse_dates=True) for a in STEP}
    for f in spots.values():f.index=pd.to_datetime(f.index,utc=True)
    frames={};audits=[]
    for row in contracts():
        sym=row['symbol'];start=pd.Timestamp(row['decision'])-pd.Timedelta(days=2);end=pd.Timestamp(row['expiry'])
        ix=pd.date_range(start,end,freq='h')
        path=ROOT/'inverse_data'/f'{sym}_klines.csv';mp=ROOT/'inverse_data'/f'{sym}_markPriceKlines.csv'
        if not path.exists() or not mp.exists():
            audits.append(dict(symbol=sym,error='No archives'));continue
        f=pd.read_csv(path,index_col=0,parse_dates=True);m=pd.read_csv(mp,index_col=0,parse_dates=True)
        f.index=pd.to_datetime(f.index,utc=True);m.index=pd.to_datetime(m.index,utc=True)
        x=pd.DataFrame(index=ix);s=spots[row['asset']].reindex(ix)
        for k in ['open','close','high','volume','quote_volume']:x['spot_'+k]=s[k]
        x['spot_executable']=s['executable'].fillna(False).astype(bool)
        for k in ['open','close','high','contracts']:x['future_'+k]=f[k]
        for k in ['open','high','close']:x['mark_'+k]=m[k]
        # Conservative valuation-only recovery. No missing price can create a fill.
        x['future_executable']=x.future_open.notna() & (x.future_contracts>0)
        x['mark_proxy']=x.mark_open.isna()
        for k in ['open','high','close']:
            ratio=(x['mark_'+k]/x['spot_'+k]).ffill()
            x['mark_'+k]=x['mark_'+k].fillna(ratio*x['spot_'+k])
        x['spot_cap']=(x.spot_quote_volume.rolling(24).mean().shift(1)*.01)
        x['future_cap']=(x.future_contracts.rolling(24).mean().shift(1)*row['face']*.01)
        audits.append(dict(symbol=sym,missing_future=int(x.future_open.isna().sum()),mark_proxy=int(x.mark_proxy.sum()),
                           missing_spot=int(x.spot_open.isna().sum())))
        frames[sym]=x
    pd.DataFrame(audits).to_csv(ROOT/'reports/inverse_data_audit.csv',index=False)
    return spots,frames


def open_lot(cash,budget,face,spot,future,spot_bps,future_bps,cap_contracts):
    """Net coin wallet matches inverse short after coin-denominated entry fees."""
    sf=spot_bps/1e4;ff=future_bps/1e4
    n=min(int(budget/(face/future*(1+ff)*spot*(1+sf))),int(cap_contracts))
    while n>0:
        c=n*face;coin=math.ceil((c/future*(1+ff)-1e-12)/.001)*.001
        cost=coin*spot*(1+sf)
        if cost<=min(cash,budget)+1e-9:break
        n-=1
    if n<=0:return 0,0.,0.,0.,0.
    wallet=coin-c/future*ff
    fee=coin*spot*sf+c/future*ff*spot
    return n,wallet,c/future,cost,fee


def close_lot(n,face,entry_reciprocal,wallet,close_n,spot,future,spot_bps,future_bps):
    """Realise only the closed contracts, sell freed collateral, retain coin dust."""
    c=close_n*face;a_close=entry_reciprocal*close_n/n
    coin_fee=c/future*future_bps/1e4
    realised=c/future-a_close
    # Matched collateral freed by this close, less fees; existing dust may also sell.
    dust=max(wallet-entry_reciprocal,0.)
    sell=math.floor((c/future-coin_fee+dust+1e-12)/.001)*.001
    cash_received=sell*spot*(1-spot_bps/1e4)
    newwallet=wallet+realised-coin_fee-sell
    return newwallet,entry_reciprocal-a_close,cash_received,coin_fee*spot+sell*spot*spot_bps/1e4


def run(spots,frames,model,start,end,spot_bps=12.,future_bps=7.,capital=100000.):
    ix=pd.date_range(start,end,freq='h',tz='UTC');rf=cash_rates(ix).to_numpy()
    cash=capital;previous=capital;states={};rows=[];orders=[];episodes=[];invalid=[]
    schedule={}
    for r in contracts():
        t=pd.Timestamp(r['decision'])+pd.Timedelta(hours=1)
        schedule.setdefault(t,[]).append(r)
    price={a:spots[a].reindex(ix).open.to_numpy() for a in STEP}
    for i,t in enumerate(ix):
        interest=cash*rf[i]/8760.;cash+=interest;fee=0.;margin=np.inf
        # Current marked equity is used only to size the total fixed entry budget.
        marked=0.
        for a,st in states.items():
            if st['n']:
                x=frames[st['row']['symbol']].loc[t]
                if pd.isna(x.mark_open):raise ValueError('Unvalued inventory')
                marked+=(st['wallet']+st['n']*st['row']['face']/x.mark_open-st['a'])*x.spot_open
            else:marked+=st['wallet']*price[a][i]
        nav_before=cash+marked
        for r in schedule.get(t,[]):
            a=r['asset'];sym=r['symbol']
            if sym not in frames:
                invalid.append(dict(symbol=sym,reason='missing contract data'));continue
            if a in states and states[a]['n']>0:raise ValueError('Overlapping maturities')
            # Retain earlier coin dust. It is never silently converted to cash.
            dust=states[a]['wallet'] if a in states else 0.
            x=frames[sym];signal_t=pd.Timestamp(r['decision'])-pd.Timedelta(hours=1);p=x.loc[signal_t]
            annual=rf[i];days=(pd.Timestamp(r['expiry'])-pd.Timedelta(hours=1)-t).total_seconds()/86400
            hurdle=2*(12+7)/1e4+(annual+.02)*days/365
            basis=p.future_close/p.spot_close-1
            good=bool(p.spot_executable) and np.isfinite(basis) and (model=='always_on' or basis>hurdle)
            budget=.4*nav_before if good else 0.
            states[a]=dict(row=r,n=0,wallet=dust,a=0.,budget=budget,entry_start=t,
                           entry_end=t+pd.Timedelta(hours=23),exit_start=pd.Timestamp(r['expiry'])-pd.Timedelta(hours=24),
                           exit_end=pd.Timestamp(r['expiry'])-pd.Timedelta(hours=1),spent=0.,signal_basis=float(basis),
                           accepted=bool(good),fee=0.,net_cash=0.,first_entry=None)
            episodes.append(dict(symbol=sym,decision=str(pd.Timestamp(r['decision'])),basis=float(basis),hurdle=hurdle,
                                 accepted=bool(good),budget=budget))
        for a,st in states.items():
            r=st['row'];sym=r['symbol'];face=r['face'];x=frames[sym]
            if t>x.index[-1]:
                # After expiry only dust remains and follows the spot price.
                if st['n']:raise ValueError('Unclosed expired contracts')
                continue
            p=x.loc[t];can=bool(p.spot_executable) and bool(p.future_executable)
            can=can and np.isfinite(p.spot_cap) and np.isfinite(p.future_cap)
            cap=min(p.spot_cap,p.future_cap) if can else 0.
            if st['entry_start']<=t<=st['entry_end'] and st['budget']>0:
                remaining_hours=int((st['entry_end']-t).total_seconds()/3600)+1
                budget=min((st['budget']-st['spent'])/remaining_hours,p.spot_cap*(1+spot_bps/1e4)) if can else 0.
                cap_n=min(p.future_cap/face,p.spot_cap/(face/p.future_open*(1+future_bps/1e4)*p.spot_open)) if can else 0.
                n,w,entry,cost,localfee=open_lot(cash,budget,face,p.spot_open,p.future_open,spot_bps,future_bps,
                                                 math.floor(cap_n)) if can else (0,0.,0.,0.,0.)
                if n:
                    cash-=cost;st['n']+=n;st['wallet']+=w;st['a']+=entry;st['spent']+=cost
                    st['fee']+=localfee;st['net_cash']-=cost;fee+=localfee
                    if st['first_entry'] is None:st['first_entry']=t
                    orders.append(dict(time=str(t),symbol=sym,side='open',contracts=n,spot=p.spot_open,future=p.future_open,
                                       cash_flow=-cost,fee=localfee,information_time=str(t-pd.Timedelta(hours=1)),
                                       capacity=cap,notional=n*face))
            if st['exit_start']<=t<=st['exit_end'] and st['n']>0:
                hours=int((st['exit_end']-t).total_seconds()/3600)+1
                close_n=min(math.ceil(st['n']/hours),math.floor(cap/face)) if can else 0
                while close_n>0:
                    _,_,trial_cash,_=close_lot(st['n'],face,st['a'],st['wallet'],close_n,
                                              p.spot_open,p.future_open,spot_bps,future_bps)
                    if trial_cash/(1-spot_bps/1e4)<=p.spot_cap+1e-7:break
                    close_n-=1
                if close_n:
                    w,entry,received,localfee=close_lot(st['n'],face,st['a'],st['wallet'],close_n,
                                                       p.spot_open,p.future_open,spot_bps,future_bps)
                    st['n']-=close_n;st['wallet']=w;st['a']=entry;cash+=received
                    st['fee']+=localfee;st['net_cash']+=received;fee+=localfee
                    orders.append(dict(time=str(t),symbol=sym,side='close',contracts=close_n,spot=p.spot_open,future=p.future_open,
                                       cash_flow=received,fee=localfee,information_time=str(t-pd.Timedelta(hours=1)),capacity=cap,notional=close_n*face))
            if t==st['exit_end'] and st['n']:
                invalid.append(dict(symbol=sym,reason='liquidity prevented scheduled close',contracts=st['n']))
                raise ValueError(invalid[-1])
            if st['n']:
                high_equity=st['wallet']+st['n']*face/p.mark_high-st['a']
                margin=min(margin,high_equity/(st['n']*face/p.mark_high))
        value=0.;gross=0.;coins={};inverse_unreal=0.
        for a,st in states.items():
            sp=price[a][i]
            if st['n']:
                p=frames[st['row']['symbol']].loc[t];u=st['n']*st['row']['face']/p.mark_open-st['a']
                value+=(st['wallet']+u)*sp;inverse_unreal+=u*sp;gross+=st['n']*st['row']['face']+st['wallet']*sp
            else:value+=st['wallet']*sp
            coins[a]=st['wallet']
        nav=cash+value
        if cash<-.01 or value<-.01 or nav<=0:raise ValueError('Cash or margin exhaustion')
        rows.append(dict(time=t,nav=nav,cash=cash,coin_equity_value=value,futures_unrealized=inverse_unreal,
                         fees=fee,interest=interest,funding=0.,gross=gross,margin_stress_ratio=margin,
                         cash_benchmark_return=rf[i]/8760.,return_=nav/previous-1,
                         wallet_btc=coins.get('BTC',0.),wallet_eth=coins.get('ETH',0.)))
        previous=nav
    ledger=pd.DataFrame(rows).set_index('time')
    return ledger,pd.DataFrame(orders),pd.DataFrame(episodes),invalid


def main():
    spots,frames=load();summaries=[]
    end='2026-06-26 07:00'
    for model in ['always_on','cost_cash_gate']:
        for sb,fb in [(12.,7.),(20.,12.),(30.,20.)]:
            ledger,orders,episodes,invalid=run(spots,frames,model,'2021-01-01',end,sb,fb)
            stem=f'inverse_{model}_cost{int(sb)}_{int(fb)}'
            save_frame(ledger,ROOT/'reports'/f'{stem}_hourly.csv');save_frame(orders,ROOT/'reports'/f'{stem}_orders.csv',index=False)
            save_frame(episodes,ROOT/'reports'/f'{stem}_episodes.csv',index=False)
            for period,a,b in [('development','2021','2022'),('later','2023','2026')]:
                h=ledger.loc[a:b].copy();initial=100000. if a=='2021' else ledger.loc[:'2022'].nav.iloc[-1]
                m=metrics(h,initial);m['cash_interest']=h.interest.sum();result=dict(model=model,spot_bps=sb,future_bps=fb,period=period,**m)
                summaries.append(result);print(result,flush=True)
    pd.DataFrame(summaries).to_csv(ROOT/'reports/inverse_summary.csv',index=False)
    (ROOT/'reports/inverse_run_identity.json').write_text(json.dumps(dict(code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               protocol_sha256=hashlib.sha256((ROOT/'inverse_protocol.json').read_bytes()).hexdigest()),indent=2))


if __name__=='__main__':main()
