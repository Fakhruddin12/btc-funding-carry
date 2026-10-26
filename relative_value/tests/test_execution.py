import numpy as np
import pandas as pd
from research import simulate,cash_ledger,summary


def example():
    index=pd.bdate_range('2020-01-01',periods=9)
    f=pd.DataFrame(index=index)
    for leg in ['a','b']:
        f[leg+'_open']=100.;f[leg+'_close']=100.;f[leg+'_dividend']=0.
        f[leg+'_adv_prior']=1e8
    f['zscore']=[-3.,-3.,0.,0.,0.,0.,0.,0.,0.]
    f['ou_cost']=f.zscore;f['pci_cost']=f.zscore;f['ou_edge']=.1;f['pci_edge']=.1
    rf=pd.Series(.0001,index=index)
    return {'a':'A','b':'B','beta':1.,'ou_valid':True,'pci_valid':True,'features':f,
            'test':index[1:],'fold':'test'},rf


def test_close_signal_executes_next_open_without_earning_preentry_gap():
    rec,rf=example();rec['features'].iloc[1,rec['features'].columns.get_loc('a_open')]=110.
    rec['features'].iloc[1,rec['features'].columns.get_loc('a_close')]=110.
    rf[:]=0
    ledger,_=simulate(rec,rf,'zscore',fee_bps=0,borrow_rate=0)
    assert np.isclose(ledger.nav.iloc[0],62500.)
    assert ledger.shares_a.iloc[0]>0 and ledger.shares_b.iloc[0]<0
    assert np.isclose(ledger.nav.iloc[1]-ledger.nav.iloc[0],ledger.shares_a.iloc[0]*(100-110))


def test_daily_cash_and_share_accounting_reconciles():
    rec,rf=example();f=rec['features'];f['a_close']+=np.arange(len(f))*.3
    f.loc[f.index[2],'a_dividend']=1.;f.loc[f.index[2],'b_dividend']=.4
    ledger,_=simulate(rec,rf,'zscore',fee_bps=10,borrow_rate=.03)
    q_old=np.zeros(2);nav_prev=62500.
    for date,row in ledger.iterrows():
        k=f.index.get_loc(date);prev=f.iloc[k-1];current=f.iloc[k]
        q_new=np.array([row.shares_a,row.shares_b]);op=np.array([current.a_open,current.b_open])
        close=np.array([current.a_close,current.b_close]);oldclose=np.array([prev.a_close,prev.b_close])
        expected=q_old@(op-oldclose)+q_new@(close-op)+row.distributions+row.interest-row.borrow-row.fees
        assert np.isclose(row.nav-nav_prev,expected,atol=1e-8)
        assert np.isclose(row.nav,row.cash+q_new@close)
        assert np.all(q_new==np.floor(q_new))
        q_old=q_new;nav_prev=row.nav
    assert ledger.state.iloc[-1]==0


def test_long_dividends_received_short_dividends_paid():
    rec,rf=example();rf[:]=0;f=rec['features']
    f.loc[f.index[2],'a_dividend']=1.;f.loc[f.index[2],'b_dividend']=.25
    ledger,_=simulate(rec,rf,'zscore',fee_bps=0,borrow_rate=0)
    q=ledger.iloc[0]
    assert np.isclose(ledger.distributions.iloc[1],q.shares_a+q.shares_b*.25)


def test_current_volume_cannot_override_prior_liquidity_limit():
    rec,rf=example();f=rec['features'];f.loc[f.index[0],['a_adv_prior','b_adv_prior']]=1.
    ledger,_=simulate(rec,rf,'zscore')
    assert ledger.state.iloc[0]==0


def test_no_future_price_change_can_modify_past_ledger():
    rec,rf=example();base,_=simulate(rec,rf,'zscore')
    changed={**rec,'features':rec['features'].copy()}
    changed['features'].loc[rec['features'].index[5]:,'a_close']*=1.2
    other,_=simulate(changed,rf,'zscore')
    np.testing.assert_allclose(base.nav.iloc[:4],other.nav.iloc[:4])


def test_idle_cash_has_zero_excess_return():
    rec,rf=example();cash=cash_ledger(rec['test'],rf)
    assert np.max(np.abs(cash['return']-cash.rf))<1e-15
    stats=summary(cash)
    assert stats['excess_sharpe'] is None


def test_transaction_cost_applies_to_both_traded_legs():
    rec,rf=example();rf[:]=0
    ledger,_=simulate(rec,rf,'zscore',fee_bps=20,borrow_rate=0)
    np.testing.assert_allclose(ledger.fees,ledger.turnover*.002)
    assert ledger.fees.sum()>0
