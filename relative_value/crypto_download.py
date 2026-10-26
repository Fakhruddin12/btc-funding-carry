"""Download official public Binance archives; retain bytes and integrity hashes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import urlopen
from urllib.error import HTTPError
from zipfile import ZipFile
from io import BytesIO
import hashlib,json,time
import pandas as pd

ROOT=Path(__file__).parent/'crypto_data'


def task(symbol,month,kind):
    if kind=='spot':
        tail=f'spot/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip'
    elif kind=='perp':
        tail=f'futures/um/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip'
    elif kind=='mark':
        tail=f'futures/um/monthly/markPriceKlines/{symbol}/1h/{symbol}-1h-{month}.zip'
    else:
        tail=f'futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip'
    url='https://data.binance.vision/data/'+tail
    path=ROOT/'raw'/f'{symbol}_{kind}_{month}.zip'
    if path.exists():raw=path.read_bytes()
    else:
        for attempt in range(3):
            try:
                with urlopen(url,timeout=40) as response:raw=response.read()
                break
            except HTTPError as exc:
                if exc.code not in [429,500,502,503,504] or attempt==2:raise
                time.sleep(2*(attempt+1))
        ZipFile(BytesIO(raw)).testzip()
        path.write_bytes(raw)
    return {'symbol':symbol,'month':str(month),'kind':kind,'source_url':url,
            'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def parse_archives():
    for symbol in ['BTCUSDT','ETHUSDT']:
        for kind in ['spot','perp','mark','funding']:
            tables=[]
            for path in sorted((ROOT/'raw').glob(f'{symbol}_{kind}_????-??.zip')):
                with ZipFile(path) as archive:
                    data=archive.read(archive.namelist()[0])
                frame=pd.read_csv(BytesIO(data),header=None)
                numeric=pd.to_numeric(frame.iloc[:,0],errors='coerce')
                frame=frame.loc[numeric.notna()].copy()
                stamp=numeric.loc[numeric.notna()].astype('int64')
                unit='us' if stamp.median()>1e14 else 'ms'
                frame.index=pd.to_datetime(stamp.to_numpy(),unit=unit,utc=True)
                if kind=='funding':
                    frame=frame.iloc[:,[1,2]];frame.columns=['interval_hours','rate']
                else:
                    frame=frame.iloc[:,[1,2,3,4,5,7]];frame.columns=['open','high','low','close','volume','quote_volume']
                frame=frame.apply(pd.to_numeric)
                tables.append(frame)
            joined=pd.concat(tables).sort_index()
            if joined.index.duplicated().any():raise ValueError(f'Duplicate events {symbol}/{kind}')
            joined.to_csv(ROOT/f'{symbol}_{kind}.csv',index_label='timestamp')
            print('parsed',symbol,kind,len(joined),joined.index[0],joined.index[-1],flush=True)


if __name__=='__main__':
    (ROOT/'raw').mkdir(parents=True,exist_ok=True)
    jobs=[(s,str(m),k) for s in ['BTCUSDT','ETHUSDT'] for m in pd.period_range('2020-01','2026-08',freq='M') for k in ['spot','perp','mark','funding']]
    records=[];errors=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(task,*job):job for job in jobs}
        for i,future in enumerate(as_completed(futures),1):
            try:records.append(future.result())
            except Exception as exc:errors.append({'job':futures[future],'error':str(exc)})
            if i%40==0:print('downloaded',i,'/',len(jobs),'errors',len(errors),flush=True)
    (ROOT/'manifest.json').write_text(json.dumps({'files':records,'errors':errors},indent=2))
    if errors:raise RuntimeError(f'{len(errors)} unavailable files; no silent substitution.')
    parse_archives()
