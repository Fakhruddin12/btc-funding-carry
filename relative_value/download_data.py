"""Download a fixed, economically motivated ETF research universe, not performance-selected pairs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json, hashlib, time
import pandas as pd

PAIRS = [
    ('SPY','IVV','S&P 500 exposure'),('VTI','ITOT','US broad equity'),
    ('IWM','IJR','US small-cap equity'),('XLB','VAW','materials'),
    ('XLE','VDE','energy'),('XLF','VFH','financials'),('XLI','VIS','industrials'),
    ('XLK','VGT','technology'),('XLP','VDC','consumer staples'),
    ('XLU','VPU','utilities'),('XLV','VHT','healthcare'),
    ('XLY','VCR','consumer discretionary'),('IYR','VNQ','US real estate'),
    ('GLD','IAU','gold'),('TLT','VGLT','long US Treasuries'),
    ('IEF','VGIT','intermediate US Treasuries')]


def download(symbol, root):
    params={'period1':int(datetime(2009,1,1,tzinfo=timezone.utc).timestamp()),
            'period2':int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp()),
            'interval':'1d','events':'div,splits','includeAdjustedClose':'true'}
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'?'+urlencode(params)
    request=Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urlopen(request,timeout=45) as response:
        raw=response.read()
    (root/'raw'/f'{symbol}.json').write_bytes(raw)
    result=json.loads(raw)['chart']['result'][0]
    quote=result['indicators']['quote'][0]
    dates=pd.to_datetime(result['timestamp'],unit='s',utc=True).tz_convert('America/New_York').date
    frame=pd.DataFrame(quote,index=pd.to_datetime(dates))
    frame['adjclose']=result['indicators']['adjclose'][0]['adjclose']
    frame['dividend']=0.
    for event in result.get('events',{}).get('dividends',{}).values():
        date=pd.Timestamp(event['date'],unit='s',tz='UTC').tz_convert('America/New_York').date()
        if pd.Timestamp(date) in frame.index:
            frame.loc[pd.Timestamp(date),'dividend']+=event['amount']
    # Yahoo's historical OHLC and dividend units are split-adjusted; do not apply splits twice.
    frame.to_csv(root/f'{symbol}.csv',index_label='date')
    return {'symbol':symbol,'source_url':url,'fetched_utc':datetime.now(timezone.utc).isoformat(),
            'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(frame),
            'start':str(frame.index[0].date()),'end':str(frame.index[-1].date()),
            'currency':result['meta'].get('currency'),'exchange_timezone':result['meta'].get('exchangeTimezoneName'),
            'split_events':list(result.get('events',{}).get('splits',{}).values())}


if __name__=='__main__':
    root=Path(__file__).parent/'data';(root/'raw').mkdir(parents=True,exist_ok=True)
    (root/'universe.json').write_text(json.dumps(PAIRS,indent=2))
    symbols=sorted({s for a,b,_ in PAIRS for s in [a,b]})
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(download,s,root) for s in symbols]
        for symbol,future in zip(symbols,futures):
            try:
                record=future.result();results.append(record)
                print(symbol,record['rows'],record['end'],flush=True)
            except Exception as exc:
                results.append({'symbol':symbol,'error':str(exc)})
                print(symbol,'FAILED',str(exc),flush=True)
    (root/'manifest.json').write_text(json.dumps(results,indent=2))
    if any('error' in r for r in results):raise RuntimeError('Some symbols failed; no silent universe changes.')
