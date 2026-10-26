"""Dependence-aware diagnostics and ledger checks; no strategy selection."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import norm
ROOT=Path(__file__).parent


def uncertainty(x,block=90,replications=2000):
    x=np.asarray(x,dtype=float);n=len(x);mean=x.mean();z=x-mean
    lag=min(block,n-2);g0=z@z/n
    lrv=g0+2*sum((1-k/(lag+1))*(z[k:]@z[:-k])/n for k in range(1,lag+1))
    se=np.sqrt(max(lrv,0)/n)
    rng=np.random.default_rng(2727+block);boot=[]
    for _ in range(replications):
        starts=rng.integers(0,n,size=int(np.ceil(n/block)))
        take=((starts[:,None]+np.arange(block))%n).ravel()[:n]
        boot.append(x[take].mean()*365)
    return dict(block_days=block,annual_arithmetic_excess=float(mean*365),
                bootstrap95_annual_mean=np.quantile(boot,[.025,.975]).tolist(),
                hac_mean_p_two_sided=float(2*norm.sf(abs(mean/se))) if se>0 else None,
                long_run_variance_sharpe=float(mean/np.sqrt(lrv)*np.sqrt(365)) if lrv>0 else None)


def analyse(path,start='2023',initial=None):
    h=pd.read_csv(path,index_col=0,parse_dates=True)
    if initial is None:initial=1e6
    base=h.loc[:str(int(start)-1)].nav.iloc[-1] if len(h.loc[:str(int(start)-1)]) else initial
    h=h.loc[start:];nav=h.nav.resample('D').last();r=nav.pct_change();r.iloc[0]=nav.iloc[0]/base-1
    cash=(1+h.cash_benchmark_return).resample('D').prod()-1
    x=r-cash
    years=[];prev=base
    for year,g in h.groupby(h.index.year):
        nv=g.nav.iloc[-1];cr=(1+g.cash_benchmark_return).prod()-1
        years.append(dict(year=int(year),days=int(len(g.nav.resample('D').last())),total_return=float(nv/prev-1),
                          cash_return=float(cr),funding=float(g.funding.sum()),fees=float(g.fees.sum()),interest=float(g.interest.sum())))
        prev=nv
    return dict(file=path.name,period_start=str(h.index[0]),period_end=str(h.index[-1]),
                diagnostics=[uncertainty(x,b) for b in [30,90]],yearly=years)


def main():
    all_results=[];audits=[]
    for pattern in ['crypto_locked_*_cost*_hourly.csv','inverse_*_cost*_hourly.csv']:
        for path in sorted((ROOT/'reports').glob(pattern)):
            if path.stat().st_size<1000:continue
            try:result=analyse(path,initial=100000. if path.name.startswith('inverse_') else 1e6)
            except Exception as e:raise RuntimeError(f'{path}: {e}')
            all_results.append(result)
            h=pd.read_csv(path,index_col=0,parse_dates=True)
            inverse=path.name.startswith('inverse_')
            if inverse:
                discrepancy=np.max(np.abs(h.nav-h.cash-h.coin_equity_value))
            else:
                discrepancy=np.max(np.abs(h.nav-h.cash-h.spot_value-h.futures_unrealized))
                assert (h.posted_collateral<=h.cash+1e-6).all()
                assert len(h)==1339*24
            assert discrepancy<1e-5
            orders=pd.read_csv(str(path).replace('_hourly.csv','_orders.csv'))
            assert (pd.to_datetime(orders.information_time)<pd.to_datetime(orders.time)).all()
            assert np.isclose(h.fees.sum(),orders.fee.sum(),rtol=1e-10)
            audit=dict(file=path.name,rows=len(h),nav_identity_max_error=float(discrepancy),
                       minimum_cash=float(h.cash.min()),fee_reconciliation_error=float(h.fees.sum()-orders.fee.sum()),
                       margin_stress_hours=int((h.margin_stress_ratio<.1).sum()))
            if inverse:
                assert (orders.notional<=orders.capacity+1e-5).all()
            else:
                audit['peak_exchange_inventory_and_collateral']=float((h.spot_value+h.posted_collateral).max())
            audits.append(audit)
    (ROOT/'reports/dependence_diagnostics.json').write_text(json.dumps(all_results,indent=2))
    (ROOT/'reports/ledger_audits.json').write_text(json.dumps(audits,indent=2))
    print('Audited',len(audits),'ledgers')
    for result in all_results:
        if 'cost12_7' in result['file']:print(result['file'],result['diagnostics'])


if __name__=='__main__':main()
