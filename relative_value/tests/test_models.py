import numpy as np
from models import fit_pci,filter_pci,manual_filter,PCIFit


def generate(n=1500,seed=7):
    rng=np.random.default_rng(seed);m=np.zeros(n);r=np.zeros(n)
    for t in range(1,n):
        m[t]=.9*m[t-1]+rng.normal(0,.01)
        r[t]=r[t-1]+rng.normal(0,.003)
    return m+r,m,r


def test_state_filter_matches_independent_recursion():
    s,_,_=generate(500);fit=PCIFit(.9,1.,.09,.01,True,0.)
    m,r,_=filter_pci(s,fit);manual=manual_filter(s,fit)
    np.testing.assert_allclose(m,manual[0],atol=1e-8)
    np.testing.assert_allclose(r,manual[1],atol=1e-8)
    np.testing.assert_allclose(m+r,s,atol=1e-8)


def test_future_observation_cannot_change_past_filtered_states():
    s,_,_=generate(500);fit=PCIFit(.9,1.,.09,.01,True,0.)
    m,_,_=filter_pci(s,fit);s[400:]+=.5
    changed,_,_=filter_pci(s,fit)
    np.testing.assert_allclose(m[:400],changed[:400],atol=1e-12)


def test_known_synthetic_model_is_recovered():
    s,m,_=generate();fit=fit_pci(s)
    assert fit.converged
    assert abs(fit.rho-.9)<.08
    filtered,_,_=filter_pci(s,fit)
    assert np.corrcoef(filtered[100:],m[100:])[0,1]>.75
    assert 0<fit.mean_reverting_fraction<1
