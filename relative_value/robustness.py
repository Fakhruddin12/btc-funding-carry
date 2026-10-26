"""Declared diagnostic variants; neither asset is reselected using these results."""
from pathlib import Path
import json
import pandas as pd
import carry,inverse
ROOT=Path(__file__).parent


def main():
    results=[]
    data,samples=carry.load_crypto();forecasts,_=carry.build_forecasts(samples,'2026-08-31 23:00')
    for keep in carry.SYMBOLS:
        f={s:x.copy() for s,x in forecasts.items()}
        for s in f:
            if s!=keep:f[s]['ewma_gate']=float('nan')
        h,o,e=carry.run(data,f,'ewma_gate','2023-01-01','2026-08-31 23:00')
        results.append(dict(strategy='funding_gate',variant='only_'+keep,**carry.metrics(h),episodes=len(e)))
        print(results[-1],flush=True)
    spots,frames=inverse.load();original=inverse.contracts;rows=original()
    for keep in ['BTC','ETH']:
        inverse.contracts=lambda:[r for r in rows if r['asset']==keep]
        h,o,e,bad=inverse.run(spots,frames,'cost_cash_gate','2021-01-01','2026-06-26 07:00')
        later=h.loc['2023':];initial=h.loc[:'2022'].nav.iloc[-1]
        results.append(dict(strategy='dated_gate',variant='only_'+keep,**carry.metrics(later,initial),
                            accepted=int(e.loc[pd.to_datetime(e.decision).dt.year>=2023,'accepted'].sum())))
        print(results[-1],flush=True)
    inverse.contracts=original
    pd.DataFrame(results).to_csv(ROOT/'reports/leave_one_asset_out.csv',index=False)
    (ROOT/'reports/robustness_notes.txt').write_text('Keep original per-asset allocation:20%spot+20%collateral for funding,40%cash budget for dated. Other slot stays cash. No reallocating to remaining asset or selecting winner from these results. Dated starts2021 to retain small physical coin dust; reported evaluation2023 onward. Funding starts flat2023 as primary.\n')


if __name__=='__main__':main()
