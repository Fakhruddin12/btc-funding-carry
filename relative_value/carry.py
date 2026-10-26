"""Funding-aware BTC/ETH spot-perpetual relative-value research, in USDT units.

No trading API, account access, order submission or live trading is included.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from research import read_french
from io_utils import save_frame

ROOT=Path(__file__).parent
SYMBOLS=['BTCUSDT','ETHUSDT']
FEATURES=['annual_rate','mean7','mean30','basis','ret1','ret7','vol7','is_eth']


def load_crypto():
    data={};samples=[];audit=[]
    for symbol in SYMBOLS:
        frames={kind:pd.read_csv(ROOT/'crypto_data'/f'{symbol}_{kind}.csv',index_col=0,parse_dates=True)
                for kind in ['spot','perp','mark','funding']}
        for frame in frames.values():
            frame.index=pd.to_datetime(frame.index,format='mixed',utc=True)
        spot,perp,mark,fund=[frames[k] for k in ['spot','perp','mark','funding']]
        index=pd.date_range('2020-01-01','2026-08-31 23:00',freq='h',tz='UTC')
        for kind,frame in [('spot',spot),('perp',perp),('mark',mark)]:
            missing=index.difference(frame.index)
            audit.append({'symbol':symbol,'kind':kind,'rows':len(frame),'missing_hours':len(missing)})
            if len(missing):raise ValueError(f'Missing {kind} hours for {symbol}: {missing[:5]}')
            if frame.reindex(index)[['open','close','high','low']].isna().any().any():
                raise ValueError('Missing prices are not silently filled.')
        f=pd.DataFrame(index=index)
        for kind,frame in [('spot',spot),('perp',perp),('mark',mark)]:
            for col in ['open','close','high','volume','quote_volume']:
                f[kind+'_'+col]=frame[col]
        f['spot_executable']=spot['executable'] if 'executable' in spot else True
        audit.append({'symbol':symbol,'kind':'spot_flagged_valuation_proxy','rows':int(spot['valuation_proxy'].sum()) if 'valuation_proxy' in spot else 0,'missing_hours':0})
        f['spot_adv_prior']=f.spot_quote_volume.rolling(24).mean().shift(1)
        f['perp_adv_prior']=f.perp_quote_volume.rolling(24).mean().shift(1)
        # The payment belongs to inventory held before the scheduled funding hour.
        # Millisecond timestamp jitter is not a tradable signal at that hour.
        payment=fund['rate'].groupby(fund.index.floor('h')).sum()
        f['payment_rate']=payment.reindex(index,fill_value=0.)
        annual=fund.rate*365*24/fund.interval_hours
        sample=pd.DataFrame(index=fund.index.floor('h')+pd.Timedelta(hours=1))
        sample['annual_rate']=annual.to_numpy()
        sample['mean7']=annual.ewm(span=21,adjust=False).mean().to_numpy()
        sample['mean30']=annual.ewm(span=90,adjust=False).mean().to_numpy()
        # Prices in the hour ending at the information-availability time.
        past=f.loc[sample.index-pd.Timedelta(hours=1)]
        sample['basis']=((past.perp_close-past.spot_close)/past.spot_close).to_numpy()
        for name,series in [('ret1',f.spot_close.pct_change(24)),('ret7',f.spot_close.pct_change(168)),
                            ('vol7',np.log(f.spot_close).diff().rolling(168).std()*np.sqrt(24*365))]:
            sample[name]=series.reindex(sample.index-pd.Timedelta(hours=1)).to_numpy()
        observed_window=f.spot_executable.astype(int).rolling(169,min_periods=169).sum().eq(169)
        valid=observed_window.reindex(sample.index-pd.Timedelta(hours=1)).fillna(False).to_numpy()
        sample.loc[~valid,['basis','ret1','ret7','vol7']]=np.nan
        sample['is_eth']=float(symbol=='ETHUSDT');sample['symbol']=symbol
        times=fund.index.asi8;ends=times+int(pd.Timedelta(days=30).value)
        right=np.searchsorted(times,ends,side='right')
        cumulative=np.r_[0.,np.cumsum(fund.rate.to_numpy())]
        future=(cumulative[right]-cumulative[np.arange(len(fund))+1])*365/30
        future[ends>times[-1]]=np.nan
        sample['target']=future
        sample['label_end']=fund.index+pd.Timedelta(days=30)
        sample=sample.dropna(subset=FEATURES)
        samples.append(sample);data[symbol]=f
    pd.DataFrame(audit).to_csv(ROOT/'reports/crypto_data_audit.csv',index=False)
    return data,pd.concat(samples).sort_index()


def build_forecasts(samples,end):
    forecasts={s:pd.DataFrame() for s in SYMBOLS};logs=[]
    end=pd.Timestamp(end,tz='UTC')
    for quarter in pd.period_range('2021Q1',end.tz_localize(None).to_period('Q'),freq='Q'):
        cutoff=quarter.start_time.tz_localize('UTC');finish=min((quarter+1).start_time.tz_localize('UTC'),end+pd.Timedelta(hours=1))
        train=samples.loc[(samples.index<cutoff)&(samples.index>=cutoff-pd.Timedelta(days=730))&
                          (samples.label_end<cutoff)&samples.target.notna()]
        test=samples.loc[(samples.index>=cutoff)&(samples.index<finish)].copy()
        if len(train)<300:continue
        assert train.label_end.max()<cutoff
        estimator=make_pipeline(StandardScaler(),Ridge(alpha=10.))
        estimator.fit(train[FEATURES],train.target)
        test['ridge_gate']=np.clip(estimator.predict(test[FEATURES]),-1.,1.)
        test['ewma_gate']=np.clip(np.minimum(test.mean7,test.mean30),-1.,1.)
        logs.append({'quarter':str(quarter),'train_samples':len(train),'max_training_label_end':str(train.label_end.max()),
                     'first_prediction':str(test.index.min()),'coefficients':estimator[-1].coef_.tolist()})
        for symbol,group in test.groupby('symbol'):
            forecasts[symbol]=pd.concat([forecasts[symbol],group])
    return forecasts,logs


def cash_rates(index):
    observations=json.loads((ROOT/'data/cash_SOFR.json').read_text())['refRates']
    f=pd.DataFrame(observations).sort_values('effectiveDate')
    annual=pd.Series(np.maximum(f.percentRate.to_numpy(dtype=float)/100.-.0025,0.)*365/360,
                     index=pd.to_datetime(f.effectiveDate.to_numpy(),utc=True)+pd.Timedelta(days=7))
    # Conservative information lag; ACT360 accrual expressed on a365-day basis.
    known=annual.reindex(index,method='ffill')
    if known.isna().any():raise ValueError('Missing cash proxy.')
    return known


def run(data,forecasts,model,start,end,spot_bps=12.,perp_bps=7.):
    idx=pd.date_range(start,end,freq='h',tz='UTC')
    rf=cash_rates(idx);n=len(idx)
    raw={s:data[s].reindex(idx) for s in SYMBOLS}
    available={s:forecasts[s].reindex(idx,method='ffill') for s in SYMBOLS}
    q=np.zeros(2);active=np.zeros(2,dtype=bool);weak=np.zeros(2,dtype=int)
    pending=None;cash=1e6;nav_previous=1e6;previous_marks=None
    entry_price=np.zeros(2);posted=np.zeros(2)
    rows=[];orders=[];episodes=[];entered={};cooldown=np.zeros(2,dtype=int)
    for i,t in enumerate(idx):
        spot=np.array([raw[s].spot_open.iloc[i] for s in SYMBOLS])
        trade=np.array([raw[s].perp_open.iloc[i] for s in SYMBOLS])
        mark=np.array([raw[s].mark_open.iloc[i] for s in SYMBOLS])
        highs=np.array([raw[s].mark_high.iloc[i] for s in SYMBOLS])
        current_funding=np.array([raw[s].payment_rate.iloc[i] for s in SYMBOLS])
        if previous_marks is None:previous_marks=mark.copy()
        asset_funding=q*mark*current_funding
        funding=float(asset_funding.sum())
        futures_pnl=float(np.sum(q*(previous_marks-mark)))
        old_short=float(np.sum(q*previous_marks))
        free_cash=max(cash-float(posted.sum()),0)
        interest=free_cash*float(rf.iloc[i])/8760.
        cash+=funding+interest;posted+=asset_funding
        unrealized=float(np.sum(q*(entry_price-mark)))
        nav_open=float(cash+q@spot+unrealized)
        fee=0.;execution_adjustment=0.;turnover=0.
        if pending is not None:
            desired=pending['active'];resize=pending['resize']
            target=q.copy()
            for j,s in enumerate(SYMBOLS):
                if not desired[j]:target[j]=0.
                elif not active[j] or resize:
                    target[j]=np.floor((nav_open*.2/spot[j])/.001)*.001
                if target[j]!=q[j]:
                    if 'spot_executable' in raw[s] and not bool(raw[s].spot_executable.iloc[i]):
                        target[j]=q[j];continue
                    # Do not execute through an unavailable/zero-volume bar.
                    if raw[s].spot_volume.iloc[max(i-1,0)]<=0 or raw[s].perp_volume.iloc[max(i-1,0)]<=0:
                        target[j]=q[j];continue
                    cap=min(raw[s].spot_adv_prior.iloc[i],raw[s].perp_adv_prior.iloc[i])*.01
                    current_units=int(round(q[j]/.001))
                    requested_units=int(round(target[j]/.001))
                    cap_units=int(np.floor(cap/max(spot[j],trade[j])/.001))
                    change_units=int(np.clip(requested_units-current_units,-cap_units,cap_units))
                    if desired[j] is False or not desired[j]:
                        # Partial close remains an active position until fully unwound.
                        pass
                    target[j]=max(current_units+change_units,0)*.001
            delta=target-q
            for j,s in enumerate(SYMBOLS):
                if abs(delta[j])<1e-10:continue
                local_fee=abs(delta[j])*(spot[j]*spot_bps+trade[j]*perp_bps)/1e4
                adjust=delta[j]*(trade[j]-mark[j])
                if delta[j]>0:
                    entry_price[j]=(q[j]*entry_price[j]+delta[j]*trade[j])/target[j]
                else:
                    realized=-delta[j]*(entry_price[j]-trade[j])
                    cash+=realized;posted[j]+=realized
                cash-=delta[j]*spot[j]+local_fee
                # One-times notional futures collateral, reset only when inventory changes.
                remaining_unrealized=target[j]*(entry_price[j]-mark[j])
                posted[j]=target[j]*mark[j]+max(-remaining_unrealized,0.)
                fee+=local_fee;execution_adjustment+=adjust
                turnover+=abs(delta[j])*(spot[j]+trade[j])
                orders.append({'time':str(t),'symbol':s,'delta_quantity':delta[j],'spot_price':spot[j],
                               'perp_price':trade[j],'fee':local_fee,'information_time':str(pending['decision_time'])})
                if q[j]==0 and target[j]>0:entered[s]={'time':t,'nav':nav_open,'funding':0.,'fees':local_fee}
                if target[j]<1e-9 and q[j]>0:
                    event=entered.pop(s,None)
                    if event:episodes.append({'symbol':s,'entry':str(event['time']),'exit':str(t),'days':(t-event['time']).total_seconds()/86400})
            q=target;active=q>1e-9
            required=q*mark+np.maximum(-q*(entry_price-mark),0.)
            posted=np.where(active,np.maximum(posted,required),0.)
            if posted.sum()>cash+1e-6:
                posted=required.copy()
            if posted.sum()>cash+1e-6:
                # A sharp spot decline can leave offsetting futures gains unrealised.
                # Realise them with an actual futures close/reopen, paying both fees.
                for j in np.argsort(-q*(entry_price-mark)):
                    if q[j]*(entry_price[j]-trade[j])<=0:continue
                    refresh_fee=2*q[j]*trade[j]*perp_bps/1e4
                    realised=q[j]*(entry_price[j]-trade[j])
                    cash+=realised-refresh_fee;entry_price[j]=trade[j]
                    fee+=refresh_fee;turnover+=2*q[j]*trade[j]
                    orders.append({'time':str(t),'symbol':SYMBOLS[j],'delta_quantity':0.,
                                   'futures_roundtrip_quantity':2*q[j],
                                   'spot_price':spot[j],'perp_price':trade[j],'fee':refresh_fee,
                                   'information_time':str(pending['decision_time']),
                                   'reason':'realise futures gains to fund collateral; no spot inventory change'})
                    required=q*mark+np.maximum(-q*(entry_price-mark),0.)
                    posted=required.copy()
                    if posted.sum()<=cash+1e-6:break
            if posted.sum()>cash+1e-6:
                raise ValueError('Insufficient cash for the declared fully reserved collateral policy.')
            pending=None
        unrealized=float(np.sum(q*(entry_price-mark)))
        nav=float(cash+q@spot+unrealized)
        short_notional=float(q@mark)
        # Simultaneous mark highs give a conservative collateral stress diagnostic.
        individual_margin=np.divide(posted+q*(entry_price-highs),q*highs,
                                    out=np.full(2,np.inf),where=q>1e-9)
        margin_ratio=float(individual_margin.min())
        if nav<=0:raise ValueError('Book equity exhausted.')
        rows.append({'time':t,'nav':nav,'return':nav/nav_previous-1,'cash':cash,'funding':funding,
                     'futures_pnl':futures_pnl,'execution_adjustment':execution_adjustment,'interest':interest,
                     'fees':fee,'turnover':turnover,'spot_value':float(q@spot),'short_notional':short_notional,
                     'gross':float(q@spot)+short_notional,'margin_stress_ratio':margin_ratio,
                     'posted_collateral':float(posted.sum()),'futures_unrealized':unrealized,
                     'q_btc':q[0],'q_eth':q[1],'cash_proxy_annual':float(rf.iloc[i]),
                     'cash_benchmark_return':float(rf.iloc[i])/8760.})
        nav_previous=nav;previous_marks=mark.copy()
        # Information at the beginning of a bar includes only the completed prior bar.
        # Orders from the 00:00 decision execute at 01:00.
        if t.hour==0 and i>0:
            desired=active.copy()
            for j,s in enumerate(SYMBOLS):
                prior=raw[s].iloc[i-1]
                if 'spot_executable' in prior and not bool(prior.spot_executable):
                    continue
                basis=(prior.perp_close-prior.spot_close)/prior.spot_close
                if model=='always_on':desired[j]=True
                else:
                    estimate=available[s].iloc[i-1]
                    forecast=float(estimate[model]) if model in estimate else np.nan
                    rate=float(rf.iloc[i]);roundtrip=2*(12.+7.)/1e4
                    expected=forecast*30/365+basis
                    hurdle=roundtrip+(2*rate+.02)*30/365
                    if not active[j]:desired[j]=np.isfinite(forecast) and expected>hurdle and basis>-.0025
                    else:
                        weak[j]=weak[j]+1 if forecast<2*rate-.01 else 0
                        desired[j]=weak[j]<3 and basis>-.01
                if cooldown[j]>0:desired[j]=False;cooldown[j]-=1
            pending={'active':desired,'resize':t.dayofweek==0,'decision_time':t}
        if rows[-1]['gross']/nav>.95:
            desired=pending['active'] if pending is not None else active.copy()
            pending={'active':desired,'resize':True,'decision_time':t}
        # Stress is observed only after this hour; emergency order uses the next open.
        if margin_ratio<.1:
            pending={'active':np.zeros(2,dtype=bool),'resize':False,'decision_time':t+pd.Timedelta(hours=1)-pd.Timedelta(milliseconds=1)}
            cooldown[:]=7
    # Scheduled liquidation at the final recorded open, with both leg costs.
    if q.any():
        spot=np.array([raw[s].spot_open.iloc[-1] for s in SYMBOLS]);trade=np.array([raw[s].perp_open.iloc[-1] for s in SYMBOLS]);mark=np.array([raw[s].mark_open.iloc[-1] for s in SYMBOLS])
        fee=float(np.sum(q*(spot*spot_bps+trade*perp_bps))/1e4)
        adjust=float(np.sum(-q*(trade-mark)))
        realized=float(np.sum(q*(entry_price-trade)))
        cash+=float(q@spot)+realized-fee
        for j,s in enumerate(SYMBOLS):
            if q[j]<=1e-9:continue
            orders.append({'time':str(idx[-1]),'symbol':s,'delta_quantity':-q[j],
                           'spot_price':spot[j],'perp_price':trade[j],
                           'fee':q[j]*(spot[j]*spot_bps+trade[j]*perp_bps)/1e4,
                           'information_time':str(idx[-1]-pd.Timedelta(hours=1)),
                           'reason':'scheduled evaluation-end liquidation'})
            event=entered.pop(s,None)
            if event:episodes.append({'symbol':s,'entry':str(event['time']),'exit':str(idx[-1]),'days':(idx[-1]-event['time']).total_seconds()/86400})
        rows[-1]['nav']=cash;rows[-1]['cash']=cash;rows[-1]['fees']+=fee;rows[-1]['execution_adjustment']+=adjust
        rows[-1]['turnover']+=float(np.sum(q*(spot+trade)))
        rows[-1]['spot_value']=0.;rows[-1]['short_notional']=0.;rows[-1]['gross']=0.
        rows[-1]['q_btc']=0.;rows[-1]['q_eth']=0.
        rows[-1]['posted_collateral']=0.;rows[-1]['futures_unrealized']=0.
        rows[-1]['margin_stress_ratio']=np.inf
        rows[-1]['return']=cash/rows[-2]['nav']-1
    return pd.DataFrame(rows).set_index('time'),pd.DataFrame(orders),pd.DataFrame(episodes)


def metrics(hourly,initial_capital=1e6):
    nav=hourly.nav.resample('D').last();ret=nav.pct_change();ret.iloc[0]=nav.iloc[0]/initial_capital-1
    cash_daily=(1+hourly.cash_benchmark_return).resample('D').prod()-1
    excess=ret-cash_daily;sd=float(excess.std(ddof=1));years=len(ret)/365
    full=np.r_[initial_capital,nav.to_numpy()]
    return {'days':len(ret),'total_return':float(nav.iloc[-1]/initial_capital-1),'cagr':float((nav.iloc[-1]/initial_capital)**(1/years)-1),
            'cash_return':float((1+cash_daily).prod()-1),'excess_sharpe':float(excess.mean()/sd*np.sqrt(365)) if sd>1e-12 else None,
            'max_drawdown_daily':float((full/np.maximum.accumulate(full)-1).min()),
            'funding_received':float(hourly.funding.sum()),'fees_paid':float(hourly.fees.sum()),
            'cash_interest':float(hourly.interest.sum()),'mean_gross_exposure':float((hourly.gross/hourly.nav).mean()),
            'minimum_stressed_cash_to_short':float(hourly.margin_stress_ratio.min()),
            'margin_stress_hours_below_10pct':int((hourly.margin_stress_ratio<.1).sum())}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['development','locked'],required=True);args=parser.parse_args()
    out=ROOT/'reports';data,samples=load_crypto()
    end='2022-12-31 23:00' if args.phase=='development' else '2026-08-31 23:00'
    start='2021-01-01' if args.phase=='development' else '2023-01-01'
    if args.phase=='locked':
        decision_path=ROOT/'crypto_locked_decision.json'
        if not decision_path.exists():raise RuntimeError('Freeze selection first.')
        decision=json.loads(decision_path.read_text())
        actual_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if actual_hash!=decision['code_sha256']:
            raise RuntimeError('Strategy code changed after the validation freeze.')
        protocol_hash=hashlib.sha256((ROOT/'crypto_protocol.json').read_bytes()).hexdigest()
        if protocol_hash!=decision['protocol_sha256']:
            raise RuntimeError('Research protocol changed after the validation freeze.')
    forecasts,logs=build_forecasts(samples,end)
    (out/f'crypto_{args.phase}_fit_log.json').write_text(json.dumps(logs,indent=2))
    summaries=[]
    for model in ['always_on','ewma_gate','ridge_gate']:
        for spot,perp in [(12.,7.),(20.,12.),(30.,20.)]:
            ledger,orders,episodes=run(data,forecasts,model,start,end,spot,perp)
            stem=f'crypto_{args.phase}_{model}_cost{int(spot)}_{int(perp)}'
            save_frame(ledger,out/f'{stem}_hourly.csv');save_frame(orders,out/f'{stem}_orders.csv',index=False);save_frame(episodes,out/f'{stem}_episodes.csv',index=False)
            result=dict(model=model,spot_bps=spot,perp_bps=perp,phase=args.phase,**metrics(ledger))
            summaries.append(result);print(result,flush=True)
    pd.DataFrame(summaries).to_csv(out/f'crypto_{args.phase}_summary.csv',index=False)


if __name__=='__main__':main()
