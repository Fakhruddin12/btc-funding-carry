"""Next-open ETF backtest with cash, shares, distributions, borrow and an explicit cash benchmark."""
from pathlib import Path
from dataclasses import asdict
import argparse,json,hashlib,warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from models import fit_pci,filter_pci
from download_data import PAIRS


ROOT=Path(__file__).parent
MODELS=['zscore','ou_cost','pci_cost']
SCENARIOS=[(5.,.01),(10.,.01),(20.,.01),(10.,.03),(10.,.05),(0.,0.)]


def read_french(path):
    lines=[]
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        first=line.split(',')[0].strip()
        if len(first)==8 and first.isdigit():
            lines.append(line)
    from io import StringIO
    frame=pd.read_csv(StringIO('\n'.join(lines)),header=None)
    frame.index=pd.to_datetime(frame.pop(0).astype(str),format='%Y%m%d')
    return frame/100.


def load_data():
    frames={}
    for symbol in sorted({s for a,b,_ in PAIRS for s in [a,b]}):
        frame=pd.read_csv(ROOT/'data'/f'{symbol}.csv',index_col=0,parse_dates=True)
        if frame.index.duplicated().any():raise ValueError(f'Duplicate dates: {symbol}')
        price=frame[['open','high','low','close','adjclose']]
        if price.isna().any().any() or (price<=0).any().any():
            raise ValueError(f'Missing/nonpositive prices: {symbol}')
        if not (frame.high>=frame[['open','close']].max(axis=1)-1e-5).all():
            raise ValueError(f'OHLC inconsistency: {symbol}')
        frames[symbol]=frame.sort_index()
    ff=read_french(ROOT/'data/ff5.csv');ff.columns=['Mkt-RF','SMB','HML','RMW','CMA','RF']
    mom=read_french(ROOT/'data/momentum.csv');ff['MOM']=mom.iloc[:,0]
    calendar=frames['SPY'].index
    rf=ff.RF.reindex(calendar)
    # No future extrapolation of missing financing observations.
    end=min(calendar[-1],ff.index[-1])
    if rf.loc['2012-01-01':end].isna().any():
        raise ValueError('Risk-free data has gaps; do not fill with future observations.')
    return frames,ff,calendar[calendar<=end]


def quarter_features(frames,calendar,q):
    test=calendar[(calendar>=q.start_time)&(calendar<=q.end_time)]
    if not len(test):return [],[]
    past=calendar[calendar<q.start_time][-504:]
    records=[];logs=[]
    for a,b,theme in PAIRS:
        raw_a,raw_b=frames[a],frames[b]
        if len(past)<400 or not past.isin(raw_a.index).all() or not past.isin(raw_b.index).all():
            logs.append({'fold':str(q),'a':a,'b':b,'eligible':False,'reason':'insufficient formation history'})
            continue
        idx=past.append(test)
        if not idx.isin(raw_a.index).all() or not idx.isin(raw_b.index).all():
            raise ValueError(f'Missing execution bars for {a}/{b} in {q}; requires investigation.')
        sa=raw_a.reindex(idx);sb=raw_b.reindex(idx)
        ya=np.log(sa.adjclose);xb=np.log(sb.adjclose)
        y,x=ya.loc[past].to_numpy(),xb.loc[past].to_numpy()
        beta=float(np.cov(y,x,ddof=1)[0,1]/np.var(x,ddof=1));alpha=float(y.mean()-beta*x.mean())
        spread=ya-alpha-beta*xb;s=spread.loc[past].to_numpy()
        corr=float(sa.adjclose.loc[past].pct_change().corr(sb.adjclose.loc[past].pct_change()))
        adv_a=float((sa.close.loc[past]*sa.volume.loc[past]).median())
        adv_b=float((sb.close.loc[past]*sb.volume.loc[past]).median())
        eligible=.5<=beta<=2 and corr>=.8 and min(adv_a,adv_b)>=5e6
        log={'fold':str(q),'a':a,'b':b,'theme':theme,'eligible':eligible,'formation_start':str(past[0].date()),
             'formation_end':str(past[-1].date()),'trading_start':str(test[0].date()),'beta':beta,'alpha':alpha,
             'correlation':corr,'median_adv_a':adv_a,'median_adv_b':adv_b}
        assert past[-1]<test[0]
        if not eligible:
            log['reason']='formation beta/correlation/liquidity rule';logs.append(log);continue
        phi=float(np.cov(s[:-1],s[1:],ddof=1)[0,1]/np.var(s[:-1],ddof=1))
        half=float(-np.log(2)/np.log(phi)) if 0<phi<1 else np.inf
        ou_valid=0<phi<1 and 1<=half<=60
        log.update({'ou_rho':phi,'ou_half_life':half,'ou_valid':ou_valid})
        pci=fit_pci(s)
        m,r,posterior_var=filter_pci(spread.to_numpy(),pci)
        pci_valid=pci.converged and 1<=pci.half_life<=60 and pci.mean_reverting_fraction>=.5
        log.update({'pci_'+k:v for k,v in asdict(pci).items()})
        log.update({'pci_half_life':pci.half_life,'pci_mr_fraction':pci.mean_reverting_fraction,'pci_valid':pci_valid})
        mean=spread.shift(1).rolling(60).mean();sd=spread.shift(1).rolling(60).std()
        f=pd.DataFrame(index=idx)
        f['zscore']=(spread-mean)/sd
        f['ou_cost']=f.zscore
        f['pci_cost']=m/pci.equilibrium_sd
        f['ou_edge']=np.abs(spread-mean)*(1-phi**20)/(1+beta) if ou_valid else 0.
        # One posterior-state-standard-error margin; not a full parameter confidence interval.
        f['pci_edge']=np.maximum(np.abs(m)-np.sqrt(np.maximum(posterior_var,0)),0)*(1-pci.rho**20)/(1+beta)
        for tag,source in [('a',sa),('b',sb)]:
            for col in ['open','close','dividend']:
                f[f'{tag}_{col}']=source[col]
            f[f'{tag}_adv_prior']=(source.close*source.volume).rolling(20).mean()
        f=f.loc[past[-1]:test[-1]].copy()
        records.append({'a':a,'b':b,'theme':theme,'beta':beta,'ou_valid':ou_valid,'pci_valid':pci_valid,
                        'features':f,'test':test,'fold':str(q)})
        logs.append(log)
    return records,logs


def desired_entry(row,model,beta,rf_known,valid):
    z=float(row[model])
    if not valid or not np.isfinite(z) or not 2<=abs(z)<4:
        return 0
    direction=-int(np.sign(z))
    if model=='zscore':return direction
    long_weight=(1. if direction==1 else beta)/(1+beta)
    short_weight=1-long_weight
    estimated_carry=.01*short_weight*20/252 + max(rf_known,0)*long_weight*20
    required=1.5*(.002+estimated_carry)
    edge=float(row['ou_edge' if model=='ou_cost' else 'pci_edge'])
    return direction if edge>required else 0


def simulate(record,rf,model,fee_bps=10.,borrow_rate=.01,slot_capital=62500.):
    f=record['features'];test=record['test'];beta=record['beta']
    valid=True if model=='zscore' else record['ou_valid'] if model=='ou_cost' else record['pci_valid']
    cash=slot_capital;q=np.zeros(2);state=0;entry_nav=None;entry_j=None;entry_day=None
    previous=f.index[0]
    pending=desired_entry(f.loc[previous],model,beta,float(rf.loc[previous]),valid)
    nav_previous=slot_capital;daily=[];trades=[]
    for j,date in enumerate(test):
        row=f.loc[date];prev=f.loc[previous]
        pc=np.array([prev.a_close,prev.b_close]);op=np.array([row.a_open,row.b_open]);cl=np.array([row.a_close,row.b_close])
        short_previous=float(np.maximum(-q*pc,0).sum())
        unencumbered=max(cash-short_previous,0)
        interest=unencumbered*float(rf.loc[date])
        borrow_cost=short_previous*borrow_rate*(date-previous).days/365.
        distribution=float(q@np.array([row.a_dividend,row.b_dividend]))
        cash+=interest-borrow_cost+distribution
        nav_open=float(cash+q@op)
        target=0 if j==len(test)-1 else pending
        fee=0.;turnover=0.
        if state and target==0:
            turnover=float(np.abs(q*op).sum());fee=turnover*fee_bps/1e4
            cash+=float(q@op)-fee
            trades.append({'fold':record['fold'],'a':record['a'],'b':record['b'],'model':model,
                           'entry':str(entry_day.date()),'exit':str(date.date()),'sessions':j-entry_j,
                           'pnl':cash-entry_nav,'return_on_slot':cash/entry_nav-1})
            q=np.zeros(2);state=0;entry_j=None
        elif not state and target and nav_open>0:
            weights=target*np.array([1.,-beta])/(1+beta)
            # Decision-time liquidity uses the preceding close's 20-day history.
            adv=np.array([prev.a_adv_prior,prev.b_adv_prior])
            gross=min(nav_open/(1+fee_bps/1e4),float(np.min(.01*adv/np.abs(weights))))
            new_q=np.sign(weights)*np.floor(np.abs(gross*weights/op))
            if np.all(np.abs(new_q)>=1):
                q=new_q;turnover=float(np.abs(q*op).sum());fee=turnover*fee_bps/1e4
                cash-=float(q@op)+fee;state=target;entry_nav=nav_open;entry_j=j;entry_day=date
        nav=float(cash+q@cl)
        if not np.isfinite(nav) or nav<=0:raise ValueError('Invalid account equity.')
        daily.append({'date':date,'nav':nav,'return':nav/nav_previous-1,'cash':cash,
                      'shares_a':q[0],'shares_b':q[1],'a_close':cl[0],'b_close':cl[1],
                      'gross':float(np.abs(q*cl).sum()),'net':float(q@cl),'turnover':turnover,
                      'fees':fee,'borrow':borrow_cost,'distributions':distribution,'interest':interest,
                      'state':state,'rf':float(rf.loc[date])})
        nav_previous=nav
        if state:
            z=float(row[model]);converged=(state==1 and z>=-.5) or (state==-1 and z<=.5)
            stop=not np.isfinite(z) or abs(z)>=4 or nav/entry_nav-1<=-.05 or j-entry_j+1>=40
            pending=0 if converged or stop else state
        else:
            pending=desired_entry(row,model,beta,float(rf.loc[date]),valid)
        previous=date
    return pd.DataFrame(daily).set_index('date'),trades


def cash_ledger(index,rf,capital=62500.):
    growth=(1+rf.reindex(index)).cumprod()
    frame=pd.DataFrame(index=index)
    frame['nav']=capital*growth;frame['return']=rf.reindex(index)
    frame['cash']=frame.nav;frame['rf']=rf.reindex(index)
    for col in ['gross','net','turnover','fees','borrow','distributions','shares_a','shares_b','state']:
        frame[col]=0.
    frame['interest']=frame.nav.diff().fillna(frame.nav.iloc[0]-capital)
    return frame


def summary(daily):
    returns=daily['return'];excess=returns-daily.rf
    equity=(1+returns).cumprod();base=np.r_[1.,equity.to_numpy()]
    sd=float(excess.std(ddof=1));n=len(daily)
    return {'sessions':n,'total_return':float(equity.iloc[-1]-1),
            'cash_total_return':float((1+daily.rf).prod()-1),
            'cagr_252':float(equity.iloc[-1]**(252/n)-1),
            'excess_sharpe':float(excess.mean()/sd*np.sqrt(252)) if sd>1e-12 else None,
            'annual_excess_mean':float(excess.mean()*252),'annual_excess_vol':sd*np.sqrt(252),
            'max_drawdown':float((base/np.maximum.accumulate(base)-1).min()),
            'mean_gross_exposure':float((daily.gross/daily.nav).mean()),
            'max_gross_exposure':float((daily.gross/daily.nav).max()),
            'mean_net_exposure':float((daily.net/daily.nav).mean()),
            'one_way_annual_turnover':float((daily.turnover/daily.nav).mean()*252)}


def evaluate(fold_records,rf,model,fee,borrow,out,phase):
    whole=[];trades=[];contributions=[];book_capital=1e6
    for fold,records,index in fold_records:
        ledgers=[]
        available={(r['a'],r['b']):r for r in records}
        for a,b,_ in PAIRS:
            if (a,b) in available:
                ledger,closed=simulate(available[(a,b)],rf,model,fee,borrow,slot_capital=book_capital/16)
                trades.extend(closed)
            else:
                ledger=cash_ledger(index,rf,capital=book_capital/16)
            contributions.append({'fold':fold,'a':a,'b':b,'pnl_over_cash':float(ledger.nav.iloc[-1]-book_capital/16*(1+rf.reindex(index)).prod()),'model':model})
            ledgers.append(ledger)
        block=pd.DataFrame(index=index)
        for col in ['nav','gross','net','turnover','fees','borrow','distributions','interest']:
            block[col]=sum(ledger[col] for ledger in ledgers)
        block['return']=block.nav.pct_change(fill_method=None)
        block.loc[index[0],'return']=block.nav.iloc[0]/book_capital-1
        block['rf']=rf.reindex(index);block['fold']=fold
        block['equity']=block.nav/1e6;book_capital=float(block.nav.iloc[-1])
        whole.append(block)
    daily=pd.concat(whole)
    stem=f'{phase}_{model}_{int(fee)}bps_borrow{int(borrow*100)}'
    daily.to_csv(out/f'{stem}_daily.csv')
    pd.DataFrame(trades).to_csv(out/f'{stem}_trades.csv',index=False)
    pd.DataFrame(contributions).to_csv(out/f'{stem}_pair_contributions.csv',index=False)
    stats=summary(daily)
    stats.update({'phase':phase,'model':model,'fee_bps':fee,'borrow_rate':borrow,
                  'completed_trades':len(trades),'trade_win_fraction':float(np.mean([t['pnl']>0 for t in trades])) if trades else None,
                  'median_holding_sessions':float(np.median([t['sessions'] for t in trades])) if trades else None})
    year=[]
    for y,group in daily.groupby(daily.index.year):year.append(dict(year=y,**summary(group)))
    pd.DataFrame(year).to_csv(out/f'{stem}_years.csv',index=False)
    # Selection occurs only on validation, never these test diagnostics.
    if fee==10 and borrow==.01:
        uncertainty_and_factors(daily,out/stem)
    return stats


def uncertainty_and_factors(daily,stem):
    r=(daily['return']-daily.rf).to_numpy();n=len(r);rng=np.random.default_rng(1729)
    starts=rng.integers(0,n,size=(2000,int(np.ceil(n/20))))
    idx=(starts[:,:,None]+np.arange(20))%n
    samples=r[idx.reshape(2000,-1)[:,:n]]
    means=samples.mean(axis=1);std=samples.std(axis=1,ddof=1)
    ratios=np.divide(means*np.sqrt(252),std,out=np.full(2000,np.nan),where=std>1e-12)
    info={'bootstrap':'circular blocks,20sessions,2000resamples,conditional on realised book returns',
          'annual_excess_mean_95pct':np.quantile(means*252,[.025,.975]).tolist(),
          'sharpe_95pct':np.nanquantile(ratios,[.025,.975]).tolist() if np.isfinite(ratios).any() else [None,None]}
    ff=read_french(ROOT/'data/ff5.csv');ff.columns=['Mkt-RF','SMB','HML','RMW','CMA','RF']
    ff['MOM']=read_french(ROOT/'data/momentum.csv').iloc[:,0]
    x=ff[['Mkt-RF','SMB','HML','RMW','CMA','MOM']].reindex(daily.index).dropna()
    if len(x)>50 and np.std(r)>1e-12:
        fit=sm.OLS(pd.Series(r,index=daily.index).reindex(x.index),sm.add_constant(x)).fit(cov_type='HAC',cov_kwds={'maxlags':20})
        info['factor_regression']={'n':int(fit.nobs),'annual_alpha':float(fit.params['const']*252),
                                   'alpha_hac20_t':float(fit.tvalues['const']),'coefficients':fit.params.to_dict()}
    stem.with_suffix('.json').write_text(json.dumps(info,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['development','locked'],required=True)
    args=parser.parse_args();out=ROOT/'reports';out.mkdir(exist_ok=True)
    frames,ff,calendar=load_data()
    if args.phase=='development':start,end='2012Q1','2021Q4'
    else:
        if not (ROOT/'locked_decision.json').exists():
            raise RuntimeError('Freeze strategy choice and code hash before opening locked evaluation.')
        start,end='2022Q1','2026Q3'
    folds=[];params=[]
    for quarter in pd.period_range(start,end,freq='Q'):
        records,logs=quarter_features(frames,calendar,quarter)
        index=calendar[(calendar>=quarter.start_time)&(calendar<=quarter.end_time)]
        if not len(index):continue
        folds.append((str(quarter),records,index));params.extend(logs)
        print(args.phase,quarter,'eligible',len(records),'PCI valid',sum(r['pci_valid'] for r in records),flush=True)
    pd.DataFrame(params).to_csv(out/f'{args.phase}_formation_parameters.csv',index=False)
    results=[]
    for model in MODELS:
        for fee,borrow in SCENARIOS:
            stats=evaluate(folds,ff.RF,model,fee,borrow,out,args.phase)
            results.append(stats)
            print(model,fee,borrow,'excess Sharpe',stats['excess_sharpe'],'return',stats['total_return'],'trades',stats['completed_trades'],flush=True)
    table=pd.DataFrame(results);table.to_csv(out/f'{args.phase}_summary.csv',index=False)
    if args.phase=='development':
        selection=[]
        for model in MODELS:
            file=out/f'development_{model}_10bps_borrow1_daily.csv'
            daily=pd.read_csv(file,index_col=0,parse_dates=True)
            val=daily.loc['2019-01-01':'2021-12-31']
            selection.append({'model':model,**summary(val)})
        pd.DataFrame(selection).to_csv(out/'validation_model_comparison.csv',index=False)


if __name__=='__main__':main()
