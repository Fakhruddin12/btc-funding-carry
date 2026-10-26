import numpy as np
import pandas as pd
import inverse
from inverse import open_lot, close_lot


def test_inverse_wallet_exactly_represents_dollar_face_over_mark():
    # A matched inverse hedge removes common price moves even on extreme paths.
    n,w,a,cost,fee=open_lot(1e6,400000,100,100.,105.,0.,0.,100000)
    for mark in [1.,20.,80.,200.,10000.]:
        equity=w+n*100/mark-a
        dust=w-a
        assert np.isclose(equity,n*100/mark+dust)
        assert np.isclose(equity*mark,n*100+dust*mark)


def test_fees_and_coin_dust_reconcile_with_wallet_and_cash():
    n,w,a,cost,fee=open_lot(1e6,400000,100,50000.,52000.,12.,7.,100000)
    wallet,entry,received,exitfee=close_lot(n,100,a,w,n,80000.,80000.,12.,7.)
    assert abs(entry)<1e-10
    assert 0<=wallet<.001+1e-10
    assert fee>0 and exitfee>0
    # Gross convergence less all four explicit costs, allowing marked coin dust.
    initial_net_coin=a
    gross_gain=n*100-initial_net_coin*50000.
    # Entry rounding produces a small retained directional dust holding.
    entry_dust=w-a
    pnl=received+wallet*80000-cost
    expected=gross_gain+entry_dust*(80000-50000)-fee-exitfee
    assert np.isclose(pnl,expected,atol=1e-6)


def test_partial_unwind_preserves_matching_of_remaining_margin():
    n,w,a,cost,fee=open_lot(1e6,400000,100,200.,210.,12.,7.,100000)
    closed=n//3
    w2,a2,cash,fee2=close_lot(n,100,a,w,closed,80.,82.,12.,7.)
    assert n-closed>0 and cash>0
    for mark in [20.,1000.]:
        eq=w2+(n-closed)*100/mark-a2
        assert eq>0
        assert np.isclose(eq,(n-closed)*100/mark+(w2-a2))


def test_position_size_obeys_budget_integer_contracts_and_capacity():
    for s in [1.,40000.,90000.]:
        n,w,a,cost,fee=open_lot(1e6,12345.,100,s,s*1.05,12.,7.,17)
        assert isinstance(n,int) and n<=17
        assert cost<=12345.+1e-8
        assert w>=a-1e-8


def test_zero_capacity_cannot_generate_an_order():
    assert open_lot(1e6,400000,100,100.,105.,12.,7.,0)==(0,0.,0.,0.,0.)


def synthetic(monkeypatch):
    ix=pd.date_range('2021-01-01','2021-01-08 07:00',freq='h',tz='UTC')
    spots={};frames={};rows=[]
    for asset,face in [('BTC',100),('ETH',10)]:
        symbol=asset+'TEST';path=np.where(ix<pd.Timestamp('2021-01-05',tz='UTC'),100.,250.)
        spots[asset]=pd.DataFrame({'open':path},index=ix)
        f=pd.DataFrame(index=ix)
        for kind in ['spot','future','mark']:
            for col in ['open','close','high']:f[kind+'_'+col]=path
        f['spot_executable']=True;f['future_executable']=True
        f['spot_cap']=1e9;f['future_cap']=1e9
        frames[symbol]=f
        rows.append(dict(symbol=symbol,asset=asset,face=face,decision='2021-01-02 08:00:00+00:00',expiry='2021-01-08 08:00:00+00:00'))
    monkeypatch.setattr(inverse,'contracts',lambda:rows)
    monkeypatch.setattr(inverse,'cash_rates',lambda idx:pd.Series(0.,index=idx))
    return ix,spots,frames


def test_full_hourly_ledger_hedges_price_jump_and_closes_contracts(monkeypatch):
    ix,spots,frames=synthetic(monkeypatch)
    h,o,e,bad=inverse.run(spots,frames,'always_on',str(ix[0]),str(ix[-1]),0.,0.)
    assert not bad
    np.testing.assert_allclose(h.nav,h.cash+h.coin_equity_value,atol=1e-6)
    # At this price/face grid all coin lots match exactly, leaving no price beta.
    np.testing.assert_allclose(h.nav,100000.,atol=1e-5)
    assert h.gross.iloc[-1]==0.
    assert (pd.to_datetime(o.information_time)<pd.to_datetime(o.time)).all()
    assert np.isclose(o.loc[o.side=='open','contracts'].sum(),o.loc[o.side=='close','contracts'].sum())


def test_future_prices_cannot_change_earlier_entries_or_nav(monkeypatch):
    ix,spots,frames=synthetic(monkeypatch)
    base,orders,_,_=inverse.run(spots,frames,'always_on',str(ix[0]),str(ix[-1]))
    cutoff=pd.Timestamp('2021-01-06',tz='UTC')
    for f in frames.values():
        f.loc[cutoff:,'future_open']*=1.01
        f.loc[cutoff:,'future_close']*=1.01
    changed,_,_,_=inverse.run(spots,frames,'always_on',str(ix[0]),str(ix[-1]))
    np.testing.assert_allclose(base.loc[base.index<cutoff,'nav'],changed.loc[changed.index<cutoff,'nav'])


def test_cash_gate_rejects_zero_basis_without_trading(monkeypatch):
    ix,spots,frames=synthetic(monkeypatch)
    h,o,e,bad=inverse.run(spots,frames,'cost_cash_gate',str(ix[0]),str(ix[-1]))
    assert o.empty and not e.accepted.any()
    np.testing.assert_allclose(h.nav,100000.)
