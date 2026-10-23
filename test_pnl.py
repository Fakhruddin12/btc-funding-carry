import unittest
import pandas as pd
import numpy as np
from pnl import replay,summarize

class LedgerTests(unittest.TestCase):
    def data(self,times,prices):
        idx=pd.DatetimeIndex(times)
        spot=pd.DataFrame({'open':prices},index=idx)
        mark=pd.DataFrame({'open':prices,'high':prices},index=idx)
        fund=pd.DataFrame(columns=['scheduled_time','rate','funding_mark_proxy','per_btc'],index=pd.DatetimeIndex([],tz='UTC'))
        return dict(spot=spot,perp=spot.copy(),mark=mark,funding=fund),idx
    def test_directional_gains_cancel_and_final_cash_reconciles(self):
        d,h=self.data(pd.date_range('2024-01-01 01:00',periods=3,freq='h',tz='UTC'),[100.,140.,80.])
        x,t,f=replay(d,h,multiple=0,lot=0)
        self.assertAlmostEqual(x.equity.iloc[-1],10000)
        self.assertAlmostEqual(x.cash.iloc[-1],10000)
        self.assertAlmostEqual(x.quantity.iloc[-1],0)
    def test_native_funding_timestamp_is_not_credited_early(self):
        d,h=self.data(pd.date_range('2024-01-01 01:00',periods=3,freq='h',tz='UTC'),[100.,100.,100.])
        ft=pd.Timestamp('2024-01-01 02:00:00.006',tz='UTC')
        d['funding']=pd.DataFrame([dict(scheduled_time=ft.floor('h'),rate=.001,funding_mark_proxy=100.,per_btc=.1)],index=[ft])
        x,t,f=replay(d,h,multiple=0,lot=0)
        self.assertAlmostEqual(x.funding.iloc[1],0)
        self.assertAlmostEqual(x.cash.iloc[-1],10005)
        self.assertEqual(len(f),1)
    def test_partial_close_preserves_entry_average_and_realizes_only_closed_quantity(self):
        h=pd.to_datetime(['2024-01-01 01:00Z','2024-02-01 01:00Z','2024-03-01 01:00Z'])
        d,h=self.data(h,[100.,200.,80.])
        x,t,f=replay(d,h,multiple=0,lot=0)
        self.assertAlmostEqual(t.realized_perp.iloc[1],-2500)
        self.assertAlmostEqual(x.perp_entry_average.iloc[1],100)
        self.assertAlmostEqual(x.cash.iloc[-1],10000)
    def test_costs_reduce_final_cash_without_double_counting_unrealized_profit(self):
        d,h=self.data(pd.date_range('2024-01-01 01:00',periods=3,freq='h',tz='UTC'),[100.,100.,100.])
        x,t,f=replay(d,h,multiple=1,lot=.001)
        costs=t[['spot_fee','perp_fee','spot_slippage','perp_slippage']].to_numpy().sum()
        self.assertAlmostEqual(x.cash.iloc[-1],10000-costs)
        self.assertTrue(np.allclose(t.new_quantity/.001,np.round(t.new_quantity/.001)))

    def test_terminal_january_marks_do_not_create_an_extra_annual_period(self):
        h=pd.to_datetime(['2024-01-01 01:00Z','2024-12-31 23:00Z','2025-01-01 00:00Z','2025-01-01 01:00Z'])
        d,h=self.data(h,[100.,110.,120.,120.])
        x,t,f=replay(d,h,multiple=0,lot=0)
        daily,annual,summary=summarize(x,t)
        self.assertEqual(annual.year.tolist(),[2024])
        self.assertAlmostEqual(annual.net_pnl.sum(),summary['net_pnl'])

if __name__=='__main__':unittest.main()
