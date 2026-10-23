"""Same unconditional carry, monthly capital rebalance, trade only quantity changes."""
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent

def replay(episodes,cost_multiple=1,initial=10000):
    wealth=initial; qprev=0.; rows=[]
    for i,r in episodes.iterrows():
        s,p=r.spot_entry,r.perp_entry
        k=cost_multiple*(.0012*s+.0007*p)
        # Solve 2*S*q + k*abs(q-q_previous) = pre-trade wealth.
        if wealth/(2*s)>=qprev:q=(wealth+k*qprev)/(2*s+k)
        else:q=(wealth-k*qprev)/(2*s-k)
        assert q>0
        entry_cost=k*abs(q-qprev)
        post=wealth-entry_cost
        assert abs(post-2*s*q)<1e-7
        gross=q*r.gross
        # Only liquidate the actual remaining quantity at the final research endpoint.
        exit_cost=cost_multiple*q*(.0012*r.spot_exit+.0007*r.perp_exit) if i==len(episodes)-1 else 0.
        end=post+gross-exit_cost
        assert end>0
        rows.append(dict(month=r.month,wealth_before=wealth,btc_quantity=q,btc_traded=abs(q-qprev),
          rebalance_cost=entry_cost,final_exit_cost=exit_cost,funding=q*r.funding,basis_pnl=q*r.basis_pnl,
          wealth_end=end,return_on_capital=end/wealth-1,
          margin_proxy_breached=bool(r.margin_proxy_breached)))
        qprev=q;wealth=end
    return pd.DataFrame(rows)

if __name__=='__main__':
    episodes=pd.read_csv(ROOT/'results'/'monthly_episodes.csv')
    rows=[]
    for multiple in [1,2]:
        trades=replay(episodes,multiple)
        trades.to_csv(ROOT/'results'/f'continuous_cost_{multiple}x.csv',index=False)
        for year,g in trades.groupby(trades.month.str[:4]):
            rows.append(dict(year=year,cost_multiple=multiple,return_on_capital=float(np.prod(1+g.return_on_capital)-1),
              funding=g.funding.sum(),basis_pnl=g.basis_pnl.sum(),costs=(g.rebalance_cost+g.final_exit_cost).sum(),
              net=g.wealth_end.iloc[-1]-g.wealth_before.iloc[0],positive_months=int((g.return_on_capital>0).sum()),months=len(g)))
    result=pd.DataFrame(rows);result.to_csv(ROOT/'results'/'continuous_annual.csv',index=False)
    print(result.to_string(index=False))
    print('Three-year capital growth (base):',replay(episodes).wealth_end.iloc[-1]/10000-1)
