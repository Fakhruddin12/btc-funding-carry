import numpy as np
import pandas as pd
import carry
import json


def sample(monkeypatch):
    index=pd.date_range('2021-01-01','2021-01-07 23:00',freq='h',tz='UTC')
    data={};forecasts={}
    for s in carry.SYMBOLS:
        f=pd.DataFrame(index=index)
        for kind in ['spot','perp','mark']:
            f[kind+'_open']=100.;f[kind+'_close']=100.;f[kind+'_high']=100.
            f[kind+'_volume']=1e5;f[kind+'_quote_volume']=1e10
        f['spot_adv_prior']=1e10;f['perp_adv_prior']=1e10;f['payment_rate']=0.
        f.loc[f.index.hour.isin([0,8,16]),'payment_rate']=.0001
        data[s]=f
        forecasts[s]=pd.DataFrame(index=index,data={'ewma_gate':.2,'ridge_gate':.2})
    monkeypatch.setattr(carry,'cash_rates',lambda idx:pd.Series(0.,index=idx))
    return index,data,forecasts


def test_equal_underlying_hedge_removes_common_price_move(monkeypatch):
    index,data,pred=sample(monkeypatch)
    for s in data:
        path=100+np.arange(len(index))*.05
        for kind in ['spot','perp','mark']:
            for col in ['open','close','high']:data[s][kind+'_'+col]=path
        data[s].payment_rate=0.
    ledger,_,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),0.,0.)
    np.testing.assert_allclose(ledger.nav,1e6,atol=1e-7)


def test_funding_credited_only_to_preexisting_inventory(monkeypatch):
    index,data,pred=sample(monkeypatch)
    ledger,orders,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),0.,0.)
    first=orders.time.min();first=pd.Timestamp(first)
    assert first.hour==1
    assert ledger.loc[:first,'funding'].sum()==0.
    expected=ledger.q_btc.shift(1,fill_value=0)*data['BTCUSDT'].mark_open*data['BTCUSDT'].payment_rate
    expected+=ledger.q_eth.shift(1,fill_value=0)*data['ETHUSDT'].mark_open*data['ETHUSDT'].payment_rate
    np.testing.assert_allclose(ledger.funding,expected,atol=1e-8)


def test_funding_is_not_counted_twice_in_nav(monkeypatch):
    index,data,pred=sample(monkeypatch)
    ledger,_,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),0.,0.)
    assert np.isclose(ledger.nav.iloc[-1]-1e6,ledger.funding.sum())


def test_both_leg_fees_and_daily_accounting(monkeypatch):
    index,data,pred=sample(monkeypatch)
    ledger,orders,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),12.,7.)
    assert ledger.fees.sum()>0
    np.testing.assert_allclose(ledger.nav,ledger.cash+ledger.spot_value+ledger.futures_unrealized,atol=1e-7)
    assert np.isclose(ledger.nav.iloc[-1]-1e6,ledger.funding.sum()+ledger.interest.sum()-ledger.fees.sum())
    assert all(pd.to_datetime(orders.information_time)<pd.to_datetime(orders.time))


def test_future_funding_change_does_not_modify_past_positions(monkeypatch):
    index,data,pred=sample(monkeypatch)
    base,_,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]))
    for s in data:data[s].loc[index[100]:,'payment_rate']=-.01
    changed,_,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]))
    np.testing.assert_allclose(base.nav.iloc[:100],changed.nav.iloc[:100])


def test_basis_and_execution_pnl_reconcile_with_total_equity(monkeypatch):
    index,data,pred=sample(monkeypatch)
    for s in data:
        spot=100+np.arange(len(index))*.03
        mark=spot+np.sin(np.arange(len(index))*.2)*.1
        data[s]['spot_open']=spot;data[s]['spot_close']=spot
        data[s]['mark_open']=mark;data[s]['mark_high']=mark+.01
        data[s]['perp_open']=mark+.02
    ledger,_,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),12.,7.)
    spot_pnl=pd.Series(0.,index=index)
    for s,col in [('BTCUSDT','q_btc'),('ETHUSDT','q_eth')]:
        spot_pnl+=ledger[col].shift(1,fill_value=0)*data[s].spot_open.diff().fillna(0)
    expected=spot_pnl+ledger.futures_pnl+ledger.execution_adjustment+ledger.funding+ledger.interest-ledger.fees
    np.testing.assert_allclose(ledger.nav.diff().fillna(ledger.nav.iloc[0]-1e6),expected,atol=1e-7)


def test_no_execution_at_an_unavailable_spot_open(monkeypatch):
    index,data,pred=sample(monkeypatch)
    blocked=pd.Timestamp('2021-01-02 01:00',tz='UTC')
    for s in data:
        data[s]['spot_executable']=True
        data[s].loc[blocked,'spot_executable']=False
    ledger,orders,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]))
    assert ledger.loc[blocked,'q_btc']==0
    assert not (pd.to_datetime(orders.time)==blocked).any()


def test_valuation_proxy_cannot_trigger_a_new_daily_signal(monkeypatch):
    index,data,pred=sample(monkeypatch)
    for s in data:
        data[s]['spot_executable']=True
        data[s].loc['2021-01-01 23:00','spot_executable']=False
    ledger,orders,_=carry.run(data,pred,'ewma_gate',str(index[0]),str(index[-1]))
    assert ledger.loc['2021-01-02','q_btc'].eq(0).all()
    assert pd.Timestamp(orders.time.min())==pd.Timestamp('2021-01-03 01:00',tz='UTC')


def test_forecast_training_purges_unfinished_future_labels():
    rng=np.random.default_rng(8);index=pd.date_range('2019-01-01','2021-03-31',freq='12h',tz='UTC')
    sample=pd.DataFrame(rng.normal(size=(len(index),len(carry.FEATURES))),index=index,columns=carry.FEATURES)
    sample['symbol']=np.where(np.arange(len(index))%2,'BTCUSDT','ETHUSDT')
    sample['target']=rng.normal(.1,.01,len(index));sample['label_end']=index+pd.Timedelta(days=30)
    base,logs=carry.build_forecasts(sample,'2021-03-31')
    sample.loc[sample.label_end>=pd.Timestamp('2021-01-01',tz='UTC'),'target']=1e6
    changed,_=carry.build_forecasts(sample,'2021-03-31')
    for s in carry.SYMBOLS:
        np.testing.assert_allclose(base[s].ridge_gate,changed[s].ridge_gate)
    assert pd.Timestamp(logs[0]['max_training_label_end'])<pd.Timestamp('2021-01-01',tz='UTC')


def test_collateral_reserve_covers_unrealized_losses(monkeypatch):
    index,data,pred=sample(monkeypatch)
    for s in data:
        path=100+np.arange(len(index))*.2
        for kind in ['spot','perp','mark']:
            for col in ['open','close','high']:data[s][kind+'_'+col]=path
    ledger,orders,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),0.,0.)
    rebalance=ledger.loc[pd.to_datetime(orders.time).unique()]
    assert (rebalance.posted_collateral+rebalance.futures_unrealized>=rebalance.short_notional-1e-6).all()
    assert (ledger.posted_collateral<=ledger.cash+1e-6).all()


def test_futures_gains_are_realised_before_they_fund_spot_rebalancing(monkeypatch):
    index,data,pred=sample(monkeypatch)
    for s in data:
        path=np.where(np.arange(len(index))<48,100.,40.)
        for kind in ['spot','perp','mark']:
            for col in ['open','close','high']:data[s][kind+'_'+col]=path
        data[s].payment_rate=0.
    ledger,orders,_=carry.run(data,pred,'always_on',str(index[0]),str(index[-1]),0.,0.)
    np.testing.assert_allclose(ledger.nav,1e6,atol=1e-7)
    assert (ledger.posted_collateral<=ledger.cash+1e-6).all()
    assert orders.get('futures_roundtrip_quantity',pd.Series()).sum()>0


def test_exit_leaves_exactly_zero_lots_and_cannot_reopen_from_dust(monkeypatch):
    for price in np.random.default_rng(13).uniform(30,90000,12):
        index,data,pred=sample(monkeypatch)
        for s in data:
            for kind in ['spot','perp','mark']:
                for col in ['open','close','high']:data[s][kind+'_'+col]=price
            pred[s].loc['2021-01-03':,['ewma_gate','ridge_gate']]=-.1
        ledger,_,_=carry.run(data,pred,'ewma_gate',str(index[0]),str(index[-1]))
        # The 00:00 decision uses the previous hour, so Jan3's changed forecast
        # first contributes to the Jan4 decision; three weak decisions end Jan6.
        after=ledger.loc['2021-01-06 01:00':,['q_btc','q_eth']]
        assert (after==0).all().all()


def test_cash_proxy_has_publication_lag_and_actual360_accrual(monkeypatch,tmp_path):
    (tmp_path/'data').mkdir()
    observations={'refRates':[{'effectiveDate':'2021-01-01','percentRate':5.},
                              {'effectiveDate':'2021-01-05','percentRate':8.}]}
    (tmp_path/'data/cash_SOFR.json').write_text(json.dumps(observations))
    monkeypatch.setattr(carry,'ROOT',tmp_path)
    ix=pd.date_range('2021-01-08','2021-01-13',freq='D',tz='UTC')
    rate=carry.cash_rates(ix)
    assert np.isclose(rate.loc['2021-01-11'],(.05-.0025)*365/360)
    assert np.isclose(rate.loc['2021-01-12'],(.08-.0025)*365/360)
    assert np.isclose(rate.iloc[0]/8760,(.05-.0025)/360/24)
