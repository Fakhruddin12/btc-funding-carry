"""Exploratory BTC spot/perpetual carry, fixed monthly holdings; not execution backtest."""
from pathlib import Path
import urllib.request, zipfile, io, hashlib, json, concurrent.futures
import time
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent
BASE='https://data.binance.vision/data/'
START='2022-01-01'
END='2025-01-01'  # January 2025 retrieved only to close December 2024; no 2025 holding assessed.

def url(kind,month):
    paths={'spot':'spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-',
           'perp':'futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-',
           'mark':'futures/um/monthly/markPriceKlines/BTCUSDT/1h/BTCUSDT-1h-',
           'funding':'futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-'}
    return BASE+paths[kind]+month+'.zip'

def fetch(task):
    kind,month=task
    dest=ROOT/'raw'/f'{kind}_{month}.zip'; source=url(kind,month)
    if not dest.exists():
        for attempt in range(4):
            try:
                with urllib.request.urlopen(source,timeout=40) as r: blob=r.read()
                break
            except Exception:
                if attempt==3: raise
                time.sleep(1+attempt)
        with zipfile.ZipFile(io.BytesIO(blob)) as z: assert z.testzip() is None
        dest.write_bytes(blob)
    blob=dest.read_bytes()
    return {'kind':kind,'month':month,'url':source,'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob)}

def load(kind,months):
    frames=[]
    for month in months:
        with zipfile.ZipFile(ROOT/'raw'/f'{kind}_{month}.zip') as z:
            blob=z.read(z.namelist()[0])
        if kind=='funding':
            f=pd.read_csv(io.BytesIO(blob));f=f.rename(columns={'calc_time':'time','last_funding_rate':'rate'})
        else:
            # Futures have a header; historical spot files do not.
            f=pd.read_csv(io.BytesIO(blob),header=0 if blob.startswith(b'open_time') else None)
            f=f.iloc[:,:5];f.columns=['time','open','high','low','close']
        raw_time=pd.to_numeric(f['time'])
        f['time']=pd.to_datetime(raw_time,unit='us' if raw_time.median()>1e14 else 'ms',utc=True)
        frames.append(f)
    result=pd.concat(frames).set_index('time').sort_index()
    assert not result.index.has_duplicates
    return result

def repair_mark(mark,hours,write_manifest=True):
    missing=hours.difference(mark.index)
    manifest=[]; additions=[]
    for day in sorted(set(missing.strftime('%Y-%m-%d'))):
        source=BASE+f'futures/um/daily/markPriceKlines/BTCUSDT/1h/BTCUSDT-1h-{day}.zip'
        dest=ROOT/'raw'/f'mark_daily_{day}.zip'
        if not dest.exists():
            with urllib.request.urlopen(source,timeout=40) as r: dest.write_bytes(r.read())
        blob=dest.read_bytes()
        with zipfile.ZipFile(io.BytesIO(blob)) as z: csv=z.read(z.namelist()[0])
        f=pd.read_csv(io.BytesIO(csv),header=0 if csv.startswith(b'open_time') else None).iloc[:,:5]
        f.columns=['time','open','high','low','close']
        f['time']=pd.to_datetime(f.time,unit='ms',utc=True)
        f=f.set_index('time');f=f.loc[f.index.isin(missing)]
        additions.append(f)
        manifest.append(dict(date=day,url=source,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob),restored_hours=len(f)))
    if additions: mark=pd.concat([mark]+additions).sort_index()
    assert not mark.index.has_duplicates
    if write_manifest: (ROOT/'results'/'repair_manifest.json').write_text(json.dumps(manifest,indent=2))
    return mark,manifest

def run():
    months=pd.date_range(START,END,freq='MS',inclusive='both').strftime('%Y-%m').tolist()
    tasks=[(k,m) for m in months for k in ['spot','perp','mark','funding']]
    manifest=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for i,row in enumerate(ex.map(fetch,tasks)):
            manifest.append(row)
            if (i+1)%20==0: print('Downloaded',i+1,'/',len(tasks),flush=True)
    (ROOT/'results'/'manifest.json').write_text(json.dumps(manifest,indent=2))
    data={k:load(k,months) for k in ['spot','perp','mark','funding']}
    # All mark hours and all 8h payments required. Trade prices required only at
    # fixed endpoints; record intermediate trade-price gaps without imputing.
    t0=pd.Timestamp(START,tz='UTC')+pd.Timedelta(hours=1)
    t1=pd.Timestamp(END,tz='UTC')+pd.Timedelta(hours=1)
    hours=pd.date_range(t0,t1,freq='h'); funds=pd.date_range(START,END,freq='8h',tz='UTC')
    data['mark'],repairs=repair_mark(data['mark'],hours)
    audit={'official_daily_mark_repairs':repairs}
    for k in ['spot','perp','mark']:
        missing=hours.difference(data[k].index)
        if k=='mark': assert len(missing)==0,(k,missing)
        audit[k]={'missing_hours':len(missing),'missing_timestamps':[str(t) for t in missing],'nonpositive_prices':int((data[k][['open','high','low','close']]<=0).any(axis=1).sum())}
        assert audit[k]['nonpositive_prices']==0
    scheduled=data['funding'].index.floor('8h')
    offsets=(data['funding'].index-scheduled).total_seconds()
    assert offsets.max()<1 and not scheduled.has_duplicates
    assert len(funds.difference(scheduled))==0
    audit['funding']={'expected_payments':len(funds),'missing_payments':0,'max_settlement_timestamp_offset_seconds':float(offsets.max()),'interval_hours':data['funding'].funding_interval_hours.unique().tolist()}
    assert data['funding'].funding_interval_hours.eq(8).all()
    # Funding settlement uses mark price; hourly mark OPEN is a boundary proxy,
    # not an independently audited exact exchange settlement mark.
    f=data['funding'].copy()
    f['scheduled_time']=scheduled
    f=f.join(data['mark']['open'].rename('mark'),on='scheduled_time')
    assert not f['mark'].isna().any()
    f['cashflow_per_btc']=f.rate*f.mark
    rows=[]
    for a,b in zip(months[:-1],months[1:]):
        entry=pd.Timestamp(a+'-01',tz='UTC')+pd.Timedelta(hours=1)
        exit=pd.Timestamp(b+'-01',tz='UTC')+pd.Timedelta(hours=1)
        s0,s1=[float(data['spot'].loc[t,'open']) for t in [entry,exit]]
        p0,p1=[float(data['perp'].loc[t,'open']) for t in [entry,exit]]
        payments=f.loc[(f.index>entry)&(f.index<exit)]
        funding=float(payments.cashflow_per_btc.sum())
        basis=(s1-p1)-(s0-p0)
        assert abs(basis-((s1-s0)+(p0-p1)))<1e-8
        assert len(payments)==3*(exit-entry).days
        assert (payments.index.hour.isin([0,8,16])).all()
        # Cost assumptions, not asserted actual historical account tiers:
        # spot taker10bp, perp taker5bp, slippage2bp per leg per execution.
        fees=.001*(s0+s1)+.0005*(p0+p1)
        slip=.0002*(s0+s1+p0+p1)
        capital=2*s0  # fully funded spot plus 100% initial short cash collateral.
        net=funding+basis-fees-slip
        mark=data['mark'].loc[(data['mark'].index>=entry)&(data['mark'].index<exit)]
        # Conservative hourly-high stress, funding received during bar excluded.
        # Easier exact per-bar sum of strictly preceding payments within holding.
        prior=pd.Series([payments.loc[payments.index<t,'cashflow_per_btc'].sum() for t in mark.index],index=mark.index)
        entry_cost=.0012*s0+.0007*p0
        equity_floor=s0-entry_cost+p0-mark.high+prior
        margin_buffer=equity_floor-.01*mark.high
        minbuffer=float(margin_buffer.min())
        rows.append(dict(month=a,entry=str(entry),exit=str(exit),spot_entry=s0,spot_exit=s1,perp_entry=p0,perp_exit=p1,
          funding=funding,basis_pnl=basis,fees=fees,slippage=slip,gross=funding+basis,net=net,capital=capital,
          return_on_capital=net/capital,excess_return_5pct=net/capital-.05*(exit-entry).total_seconds()/86400/365,
          margin_proxy_min_buffer=minbuffer,margin_proxy_breached=minbuffer<=0,payment_count=len(payments),positive_funding_share=float((payments.rate>0).mean())))
    episodes=pd.DataFrame(rows);episodes.to_csv(ROOT/'results'/'monthly_episodes.csv',index=False)
    # Year averages use the same fixed one BTC per month, not compounding.
    episodes['year']=episodes.month.str[:4]
    annual=episodes.groupby('year').agg(months=('month','count'),funding=('funding','sum'),basis_pnl=('basis_pnl','sum'),costs=('fees','sum'),slippage=('slippage','sum'),net=('net','sum'),positive_months=('net',lambda x:int((x>0).sum())),sum_monthly_capital_returns=('return_on_capital','sum'),excess_5pct=('excess_return_5pct','sum'))
    annual['compounded_capital_return']=episodes.groupby('year').return_on_capital.apply(lambda r:float(np.prod(1+r)-1))
    annual.to_csv(ROOT/'results'/'annual_summary.csv')
    summary={'scope':'2022-2024 exploratory monthly price-proxy test, 1 BTC each leg; no fitted signal',
      'months':len(episodes),'positive_months':int((episodes.net>0).sum()),'negative_months':int((episodes.net<0).sum()),
      'worst_month_return':float(episodes.return_on_capital.min()),'best_month_return':float(episodes.return_on_capital.max()),
      'margin_proxy_breaches':int(episodes.margin_proxy_breached.sum()),'median_cost_fraction_spot':float(((episodes.fees+episodes.slippage)/episodes.spot_entry).median()),'audit':audit}
    (ROOT/'results'/'summary.json').write_text(json.dumps(summary,indent=2))
    print(annual.to_string(),flush=True);print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':run()
