"""Recover incomplete monthly dated-futures archives from official daily files."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
from zipfile import ZipFile
from io import BytesIO
import hashlib,json,os
import pandas as pd
from inverse_download import contracts,ROOT


def repair(job):
    row,kind,day=job;sym=row['symbol']
    url=f'https://data.binance.vision/data/futures/cm/daily/{kind}/{sym}/1h/{sym}-1h-{day}.zip'
    path=ROOT/'raw'/f'{sym}_{kind}_{day}.zip'
    if not path.exists():path.write_bytes(urlopen(url,timeout=30).read())
    raw=path.read_bytes()
    with ZipFile(BytesIO(raw)) as z:f=pd.read_csv(BytesIO(z.read(z.namelist()[0])),header=None)
    stamps=pd.to_numeric(f.iloc[:,0],errors='coerce');f=f.loc[stamps.notna()].copy()
    f.index=pd.to_datetime(stamps.dropna().astype('int64').to_numpy(),unit='ms',utc=True)
    f=f.iloc[:,[1,2,3,4,5,7]].apply(pd.to_numeric);f.columns=['open','high','low','close','contracts','coin_volume']
    return sym,kind,f,dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


if __name__=='__main__':
    jobs=[]
    for r in contracts():
        ix=pd.date_range(pd.Timestamp(r['decision'])-pd.Timedelta(days=2),pd.Timestamp(r['expiry']),freq='h')
        for kind in ['klines','markPriceKlines']:
            p=ROOT/f"{r['symbol']}_{kind}.csv";f=pd.read_csv(p,index_col=0,parse_dates=True)
            missing=ix.difference(f.index)
            for day in sorted(set(missing.strftime('%Y-%m-%d'))):jobs.append((r,kind,day))
    grouped={};records=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for sym,kind,f,record in pool.map(repair,jobs):
            grouped.setdefault((sym,kind),[]).append(f);records.append(record)
    for (sym,kind),tables in grouped.items():
        p=ROOT/f'{sym}_{kind}.csv';f=pd.read_csv(p,index_col=0,parse_dates=True)
        f=pd.concat([f]+tables).sort_index();f=f.loc[~f.index.duplicated(keep='first')]
        temp=p.with_suffix('.building.csv');f.to_csv(temp,index_label='time');os.replace(temp,p)
    (ROOT/'daily_repair_manifest.json').write_text(json.dumps(records,indent=2));print('Daily archive repairs',len(records))
