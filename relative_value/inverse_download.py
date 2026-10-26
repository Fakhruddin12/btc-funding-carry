"""Official dated COIN-M archives. No authentication or trading endpoints."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen
from urllib.error import HTTPError
from zipfile import ZipFile
from io import BytesIO
import hashlib, json, time
import pandas as pd

ROOT = Path(__file__).parent / 'inverse_data'


def contracts():
    rows = []
    for quarter in pd.period_range('2021Q1', '2026Q2', freq='Q'):
        days = pd.date_range(quarter.end_time.normalize() - pd.Timedelta(days=6), quarter.end_time.normalize())
        expiry = days[days.dayofweek == 4][-1].tz_localize('UTC') + pd.Timedelta(hours=8)
        for asset, face in [('BTC', 100), ('ETH', 10)]:
            rows.append(dict(symbol=f'{asset}USD_{expiry:%y%m%d}', asset=asset, face=face,
                             expiry=str(expiry), decision=str(expiry - pd.Timedelta(days=60))))
    return rows


def fetch(row, month, kind):
    symbol = row['symbol']
    url = f'https://data.binance.vision/data/futures/cm/monthly/{kind}/{symbol}/1h/{symbol}-1h-{month}.zip'
    path = ROOT / 'raw' / f'{symbol}_{kind}_{month}.zip'
    if path.exists():
        raw = path.read_bytes()
    else:
        for attempt in range(3):
            try:
                raw = urlopen(url, timeout=30).read()
                break
            except HTTPError as exc:
                if exc.code == 404:
                    return dict(symbol=symbol, kind=kind, month=str(month), url=url, unavailable=True)
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        if ZipFile(BytesIO(raw)).testzip() is not None:
            raise ValueError('Corrupt zip')
        path.write_bytes(raw)
    return dict(symbol=symbol, kind=kind, month=str(month), url=url,
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def parse():
    for row in contracts():
        for kind in ['klines', 'markPriceKlines']:
            tables = []
            for path in sorted((ROOT / 'raw').glob(f"{row['symbol']}_{kind}_????-??.zip")):
                with ZipFile(path) as z:
                    frame = pd.read_csv(BytesIO(z.read(z.namelist()[0])), header=None)
                stamps = pd.to_numeric(frame.iloc[:, 0], errors='coerce')
                frame = frame.loc[stamps.notna()].copy()
                frame.index = pd.to_datetime(stamps.dropna().astype('int64').to_numpy(), unit='ms', utc=True)
                frame = frame.iloc[:, [1, 2, 3, 4, 5, 7]].apply(pd.to_numeric)
                frame.columns = ['open', 'high', 'low', 'close', 'contracts', 'coin_volume']
                tables.append(frame)
            if not tables:
                continue
            joined = pd.concat(tables).sort_index()
            if joined.index.duplicated().any():
                raise ValueError('Duplicate contract hours')
            joined.to_csv(ROOT / f"{row['symbol']}_{kind}.csv", index_label='time')


if __name__ == '__main__':
    (ROOT / 'raw').mkdir(parents=True, exist_ok=True)
    rows = contracts()
    (ROOT / 'contracts.json').write_text(json.dumps(rows, indent=2))
    jobs = []
    for row in rows:
        a = (pd.Timestamp(row['decision']) - pd.Timedelta(days=2)).tz_localize(None).to_period('M')
        b = pd.Timestamp(row['expiry']).tz_localize(None).to_period('M')
        jobs.extend((row, str(month), kind) for month in pd.period_range(a, b, freq='M')
                    for kind in ['klines', 'markPriceKlines'])
    records = []; errors = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch, *job): job for job in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                records.append(future.result())
            except Exception as exc:
                errors.append(dict(job=str(futures[future]), error=str(exc)))
            if i % 40 == 0:
                print(i, '/', len(jobs), 'errors', len(errors), flush=True)
    (ROOT / 'manifest.json').write_text(json.dumps(dict(files=records, errors=errors), indent=2))
    if errors:
        raise RuntimeError(errors)
    parse()
    print('Parsed', len(rows), 'declared contracts', flush=True)
