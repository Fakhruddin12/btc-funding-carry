"""Descriptive performance and dependence-aware inference. No strategy optimization."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
import numpy as np
from scipy.stats import norm
from study import load,fetch
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'/'kpis';OUT.mkdir(parents=True,exist_ok=True)
YEAR=365.25
BOOTSTRAPS=10000

def hac(x,lag=30):
    x=np.asarray(x,float);n=len(x);z=x-x.mean()
    g0=float(z@z/n)
    longvar=g0+2*sum((1-j/(lag+1))*float(z[j:]@z[:-j]/n) for j in range(1,min(lag,n-1)+1))
    assert longvar>0
    se=np.sqrt(longvar/n);stat=x.mean()/se
    return dict(mean_annual=x.mean()*YEAR,hac_lag=lag,hac_t=stat,hac_p_two_sided=2*norm.sf(abs(stat)),mean_ci_low=(x.mean()-1.96*se)*YEAR,mean_ci_high=(x.mean()+1.96*se)*YEAR,hac_adjusted_ratio=x.mean()*np.sqrt(YEAR/longvar),effective_sample_size=n*g0/longvar)

def block_bootstrap(x,L,reps=BOOTSTRAPS,seed=16):
    x=np.asarray(x,float);n=len(x)
    extended=np.r_[x,x[:L]];cs=np.r_[0,np.cumsum(extended)]
    sq=np.r_[0,np.cumsum(extended**2)]
    sums=cs[np.arange(n)+L]-cs[np.arange(n)]
    squares=sq[np.arange(n)+L]-sq[np.arange(n)]
    rng=np.random.default_rng(seed);full,rem=divmod(n,L)
    starts=rng.integers(n,size=(reps,full))
    total=sums[starts].sum(axis=1);total2=squares[starts].sum(axis=1)
    if rem:
        st=rng.integers(n,size=reps)
        total+=cs[st+rem]-cs[st];total2+=sq[st+rem]-sq[st]
    mean=total/n;variance=(total2-n*mean**2)/(n-1)
    sharpe=mean*np.sqrt(YEAR)/np.sqrt(variance)
    return dict(block_days=L,bootstrap_replicates=reps,mean_ci_low=float(np.quantile(mean*YEAR,.025)),mean_ci_high=float(np.quantile(mean*YEAR,.975)),sharpe_ci_low=float(np.quantile(sharpe,.025)),sharpe_ci_high=float(np.quantile(sharpe,.975)))

def daily_samples(tag):
    h=pd.read_csv(ROOT/'results'/'pnl'/tag/'hourly_1x.csv.gz')
    h.index=pd.to_datetime(h.timestamp,utc=True)
    d=h.loc[h.index.hour==1].copy()
    assert (d.index.to_series().diff().dropna()==pd.Timedelta(days=1)).all()
    assert d.spot_stale_hours.eq(0).all()
    return d

def spot_benchmark(spot,grid,kind):
    # All price information for momentum decisions is at least 25 hours old.
    cash=10000.;q=0.;nav=[];trades=0
    for i,t in enumerate(grid):
        p=float(spot.loc[t,'open'])
        if i==len(grid)-1:want=False
        elif kind=='buy_hold':want=True
        else:
            prior=t.normalize()-pd.Timedelta(days=1)
            want=bool(spot.loc[prior,'open']>spot.loc[prior-pd.Timedelta(days=20),'open'])
        if want and q==0:
            qnew=np.floor((cash/(p*1.0012)+1e-12)/.001)*.001
            cash-=qnew*p*1.0012;q=qnew;trades+=1
        elif not want and q>0:
            cash+=q*p*.9988;q=0.;trades+=1
        nav.append(cash+q*p)
    assert q==0 and cash>=0
    return np.asarray(nav),trades

def basic_kpis(nav,rf,postentry=None):
    nav=np.asarray(nav,float)
    r=nav/np.r_[10000.,nav[:-1]]-1
    excess=r-rf
    days=len(r);ret=nav[-1]/10000-1;cagr=(1+ret)**(YEAR/days)-1
    path=np.r_[10000.,[postentry] if postentry is not None else [],nav]
    dd=path/np.maximum.accumulate(path)-1
    vol=np.std(r,ddof=1)*np.sqrt(YEAR)
    mdd=float(dd.min())
    return dict(observations=days,total_return=ret,cagr=cagr,annual_volatility=vol,zero_rf_ratio=float(r.mean()/r.std(ddof=1)*np.sqrt(YEAR)),sofr_excess_sharpe=float(excess.mean()/excess.std(ddof=1)*np.sqrt(YEAR)),hac30_excess_ratio=hac(excess)['hac_adjusted_ratio'],maximum_daily_drawdown=mdd,calmar_ratio=cagr/abs(mdd) if mdd else None,positive_days=int((r>0).sum()),positive_day_fraction=float((r>0).mean()),worst_day=float(r.min()),best_day=float(r.max()),net_pnl=float(nav[-1]-10000),final_equity=float(nav[-1]),lag1_return_autocorrelation=float(pd.Series(r).autocorr(1)),lag30_return_autocorrelation=float(pd.Series(r).autocorr(30)))

def run():
    warmup=fetch(('spot','2021-12'))
    raw=ROOT/'raw'/'sofr_2021_2026.json';source=json.loads(raw.read_text())
    rates=pd.DataFrame(source['refRates']).sort_values('effectiveDate')
    rates.index=pd.to_datetime(rates.effectiveDate,utc=True)
    rates=rates.percentRate.astype(float)/100
    # Retrospective effective-day, ACT/360 daily accrual proxy. No signal uses SOFR.
    # Business-day rate carried across weekends. This is not an investable account.
    summary=[];inference=[];confidence=[];provenance={'sofr_url':'https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2021-12-01&endDate=2026-01-01','sofr_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'warmup':warmup}
    for tag in ['development','validation_2025']:
        d=daily_samples(tag);grid=d.index
        months=pd.date_range(grid[0].normalize().replace(day=1)-pd.offsets.MonthBegin(1),grid[-1].normalize().replace(day=1),freq='MS').strftime('%Y-%m').tolist()
        spot=load('spot',months)
        starts=grid[:-1].normalize()
        rf=rates.reindex(starts,method='ffill').to_numpy()/360
        assert np.isfinite(rf).all()
        navs={'carry':d.equity.to_numpy(),'buy_hold':spot_benchmark(spot,grid,'buy_hold')[0],'momentum20':spot_benchmark(spot,grid,'momentum20')[0]}
        rfs={'sofr':rf,'cash5':np.full(len(rf),1.05**(1/YEAR)-1),'idle_cash':np.zeros(len(rf))}
        for name,returns in rfs.items():navs[name]=np.r_[10000,10000*np.cumprod(1+returns)]
        daily=pd.DataFrame({'timestamp':grid[1:].astype(str),'sofr_daily':rf})
        returns={}
        for name,nav in navs.items():
            nav=np.asarray(nav)
            r=nav[1:]/np.r_[10000.,nav[1:-1]]-1
            returns[name]=r
            daily[name+'_equity']=nav[1:];daily[name+'_return']=r
            if name not in rfs:
                row=basic_kpis(nav[1:],rf,postentry=nav[0]);row.update(sample=tag,strategy=name)
                if name=='carry':
                    hourly=pd.read_csv(ROOT/'results'/'pnl'/tag/'hourly_1x.csv.gz')
                    values=np.r_[10000.,hourly.equity.to_numpy()]
                    row['maximum_hourly_drawdown']=float(np.min(values/np.maximum.accumulate(values)-1))
                    hv=hourly.equity.to_numpy()[1:]
                    hr=hv/np.r_[10000.,hv[:-1]]-1
                    ht=pd.to_datetime(hourly.timestamp,utc=True)
                    hrf=rates.reindex(pd.DatetimeIndex(ht.iloc[:-1]).normalize(),method='ffill').to_numpy()/360/24
                    he=hr-hrf
                    row['hourly_annual_volatility']=float(hr.std(ddof=1)*np.sqrt(YEAR*24))
                    row['hourly_zero_rf_ratio']=float(hr.mean()/hr.std(ddof=1)*np.sqrt(YEAR*24))
                    row['hourly_sofr_excess_sharpe']=float(he.mean()/he.std(ddof=1)*np.sqrt(YEAR*24))
                    tx=pd.read_csv(ROOT/'results'/'pnl'/tag/'trades_1x.csv')
                    notional=(tx.quantity_change.abs()*(tx.spot_reference+tx.perp_reference)).sum()
                    row['annual_two_leg_turnover']=float(notional/hourly.equity.mean()/(len(r)/YEAR))
                row['benchmark_sofr_total_return']=float(navs['sofr'][-1]/10000-1)
                summary.append(row)
        daily.to_csv(OUT/f'{tag}_daily_comparison.csv',index=False)
        for benchmark in ['idle_cash','sofr','cash5','buy_hold','momentum20']:
            difference=returns['carry']-returns[benchmark]
            for lag in [7,30,90]:
                row=hac(difference,lag);row.update(sample=tag,benchmark=benchmark);inference.append(row)
                boot=block_bootstrap(difference,lag);boot.update(sample=tag,benchmark=benchmark);confidence.append(boot)
    pd.DataFrame(summary).to_csv(OUT/'performance_metrics.csv',index=False)
    pd.DataFrame(inference).to_csv(OUT/'hac_inference.csv',index=False)
    pd.DataFrame(confidence).to_csv(OUT/'block_bootstrap_intervals.csv',index=False)
    (OUT/'source_manifest.json').write_text(json.dumps(provenance,indent=2))
    print(pd.DataFrame(summary)[['sample','strategy','total_return','cagr','annual_volatility','zero_rf_ratio','sofr_excess_sharpe','hac30_excess_ratio','maximum_daily_drawdown','benchmark_sofr_total_return']].to_string(index=False))
    print(pd.DataFrame(inference).query('hac_lag==30')[['sample','benchmark','mean_annual','hac_t','hac_p_two_sided','mean_ci_low','mean_ci_high','effective_sample_size']].to_string(index=False))
    print(pd.DataFrame(confidence).query('block_days==30')[['sample','benchmark','mean_ci_low','mean_ci_high','sharpe_ci_low','sharpe_ci_high']].to_string(index=False))

if __name__=='__main__':run()
