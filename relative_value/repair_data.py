"""Reconcile missing monthly observations with official daily archives.

Unavailable spot prints are never executable. A flagged previous-basis/mark
proxy is used only to value existing inventory when spot prints are absent.
"""
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
import json,hashlib

ROOT=Path(__file__).parent/'crypto_data'


def save_csv(frame,path):
    temporary=path.with_suffix('.building.csv')
    frame.to_csv(temporary,index_label='timestamp')
    check=pd.read_csv(temporary,index_col=0)
    if len(check)!=len(frame):raise ValueError('Incomplete processed-data write.')
    temporary.replace(path)


def daily(symbol,kind,day):
    if kind=='spot':tail=f'spot/daily/klines/{symbol}/1h/{symbol}-1h-{day}.zip'
    else:tail=f'futures/um/daily/{"markPriceKlines" if kind=="mark" else "indexPriceKlines"}/{symbol}/1h/{symbol}-1h-{day}.zip'
    url='https://data.binance.vision/data/'+tail
    path=ROOT/'raw'/f'{symbol}_{kind}_daily_{day}.zip'
    raw=path.read_bytes() if path.exists() else urlopen(url,timeout=40).read()
    path.write_bytes(raw)
    archive=ZipFile(BytesIO(raw));f=pd.read_csv(BytesIO(archive.read(archive.namelist()[0])),header=None)
    stamp=pd.to_numeric(f.iloc[:,0],errors='coerce');f=f.loc[stamp.notna()].copy();stamp=stamp.loc[stamp.notna()]
    f.index=pd.to_datetime(stamp.to_numpy().astype('int64'),unit='us' if stamp.median()>1e14 else 'ms',utc=True)
    f=f.iloc[:,[1,2,3,4,5,7]].apply(pd.to_numeric);f.columns=['open','high','low','close','volume','quote_volume']
    return f,{'symbol':symbol,'kind':kind,'day':str(day),'url':url,'sha256':hashlib.sha256(raw).hexdigest()}


if __name__=='__main__':
    from crypto_download import parse_archives
    parse_archives()
    index=pd.date_range('2020-01-01','2026-08-31 23:00',freq='h',tz='UTC')
    frames={};jobs=[];records=[];audit=[]
    for symbol in ['BTCUSDT','ETHUSDT']:
        for kind in ['spot','mark']:
            f=pd.read_csv(ROOT/f'{symbol}_{kind}.csv',index_col=0,parse_dates=True)
            frames[(symbol,kind)]=f
            missing=index.difference(f.index)
            jobs.extend((symbol,kind,str(day.date())) for day in missing.floor('D').unique())
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda job:daily(*job),jobs))
    for job,(patch,record) in zip(jobs,results):
        symbol,kind,_=job;frame=frames[(symbol,kind)]
        missing=index.difference(frame.index);add=patch.loc[patch.index.intersection(missing)]
        frames[(symbol,kind)]=pd.concat([frame,add]).sort_index();records.append(record)
    for symbol in ['BTCUSDT','ETHUSDT']:
        mark=frames[(symbol,'mark')]
        if len(index.difference(mark.index)):raise ValueError('Mark-price gaps remain after daily reconciliation.')
        save_csv(mark,ROOT/f'{symbol}_mark.csv')
        spot=frames[(symbol,'spot')];missing=index.difference(spot.index)
        spot['executable']=True;spot['valuation_proxy']=False
        for date in missing:
            before=spot.loc[spot.index<date].iloc[-1]
            previous_date=spot.index[spot.index<date][-1]
            ratio=float(before.close/mark.loc[previous_date,'close'])
            patch=mark.loc[[date]].copy()
            patch[['open','high','low','close']]*=ratio
            patch['volume']=0.;patch['quote_volume']=0.
            patch['executable']=False;patch['valuation_proxy']=True
            spot=pd.concat([spot,patch]).sort_index()
        if len(index.difference(spot.index)):raise ValueError('Valuation gaps remain.')
        save_csv(spot,ROOT/f'{symbol}_spot.csv')
        audit.append({'symbol':symbol,'spot_composite_valuation_hours':len(missing),'mark_hours_recovered':len(mark)-len(pd.read_csv(ROOT/f'{symbol}_mark.csv'))})
        print(symbol,'flagged spot valuation proxies',len(missing),'mark coverage',len(mark),flush=True)
    (ROOT/'repair_manifest.json').write_text(json.dumps({'daily_sources':records,'notes':'Daily archive observations fill missing monthly records. Where no spot print exists, prior observed spot/mark ratio times current mark values existing inventory; those hours cannot execute. The unavailable composite-index archive was not substituted as observed data.'},indent=2))
