import unittest
import pandas as pd
from continuous import replay

class AccountingTests(unittest.TestCase):
    def episodes(self):
        return pd.DataFrame([dict(month=f'2024-{i+1:02d}',spot_entry=s,perp_entry=s+2,spot_exit=t,perp_exit=t+2,gross=0.,funding=0.,basis_pnl=0.,margin_proxy_breached=False) for i,(s,t) in enumerate([(100.,120.),(120.,80.),(80.,100.)])])
    def test_price_direction_alone_generates_no_profit(self):
        r=replay(self.episodes(),cost_multiple=0)
        self.assertTrue((abs(r.wealth_end-10000)<1e-8).all())
    def test_unchanged_quantity_avoids_monthly_roundtrips(self):
        e=self.episodes()
        e[['spot_entry','spot_exit']]=100.;e[['perp_entry','perp_exit']]=102.
        r=replay(e)
        self.assertLess(abs(r.btc_traded.iloc[1:].sum()),1e-8)
        self.assertAlmostEqual(10000-r.wealth_end.iloc[-1],r.rebalance_cost.sum()+r.final_exit_cost.sum())
    def test_spot_and_collateral_equal_post_cost_capital(self):
        e=self.episodes();r=replay(e)
        for i,row in r.iterrows():
            self.assertAlmostEqual(row.wealth_before-row.rebalance_cost,2*e.spot_entry.iloc[i]*row.btc_quantity)

if __name__=='__main__':unittest.main()
