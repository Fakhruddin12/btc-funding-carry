import pandas as pd
import concurrent.futures,json
from study import fetch,ROOT
months=pd.date_range('2025-02-01','2026-01-01',freq='MS').strftime('%Y-%m').tolist()
tasks=[(k,m) for m in months for k in ['spot','perp','mark','funding']]
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    for i,row in enumerate(ex.map(fetch,tasks)):
        rows.append(row)
        if (i+1)%8==0:print(i+1,'/',len(tasks),flush=True)
(ROOT/'results'/'pnl_validation_download_manifest.json').write_text(json.dumps(rows,indent=2))
