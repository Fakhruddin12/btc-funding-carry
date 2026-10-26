"""Conditional-hedge-ratio partial cointegration, inspired by Clegg & Krauss.

This implements the state decomposition, not their joint-regression estimation
or likelihood-ratio screening procedure. Filtering is causal; no smoothed states
are used for signals.
"""
from dataclasses import dataclass, asdict
import numpy as np
from scipy.optimize import minimize
from statsmodels.tsa.statespace.mlemodel import MLEModel


class TransientPermanentModel(MLEModel):
    def __init__(self, endog):
        super().__init__(np.asarray(endog), k_states=2, k_posdef=2)
        self.ssm['design']=np.array([[1.,1.]])
        self.ssm['selection']=np.eye(2)
        self.ssm['obs_cov']=np.array([[1e-9]])
        self.loglikelihood_burn=1

    def update(self, params, **kwargs):
        rho,qm,qr=np.asarray(params)
        self.ssm['transition']=np.diag([rho,1.])
        self.ssm['state_cov']=np.diag([qm,qr])
        self.ssm.initialize_known(np.zeros(2),np.diag([qm/(1-rho*rho),1e6]))


@dataclass
class PCIFit:
    rho: float
    qm: float
    qr: float
    scale: float
    converged: bool
    nll: float

    @property
    def half_life(self):
        return -np.log(2)/np.log(self.rho)

    @property
    def mean_reverting_fraction(self):
        # Share of unconditional one-day spread-innovation variance, not level variance.
        return 2*self.qm/(2*self.qm+(1+self.rho)*self.qr)

    @property
    def equilibrium_sd(self):
        return self.scale*np.sqrt(self.qm/(1-self.rho*self.rho))


def fit_pci(spread):
    spread=np.asarray(spread,dtype=float)
    scale=max(float(np.std(np.diff(spread),ddof=1)),1e-8)
    model=TransientPermanentModel(spread/scale)
    def objective(theta):
        rho=theta[0];qm,qr=np.exp(theta[1:])
        value=-model.loglike([rho,qm,qr],transformed=True)
        return value if np.isfinite(value) else 1e30
    candidates=[]
    for rho in [.8,.98]:
        fit=minimize(objective,[rho,np.log(.5),np.log(.5)],method='L-BFGS-B',
                     bounds=[(.05,.995),(-16,5),(-16,5)],options={'maxiter':150,'ftol':1e-10})
        candidates.append(fit)
    valid=[f for f in candidates if f.success and np.isfinite(f.fun)]
    best=min(valid or candidates,key=lambda f:f.fun)
    return PCIFit(float(best.x[0]),float(np.exp(best.x[1])),float(np.exp(best.x[2])),
                  scale,bool(best.success),float(best.fun))


def filter_pci(spread, fit):
    model=TransientPermanentModel(np.asarray(spread)/fit.scale)
    result=model.filter([fit.rho,fit.qm,fit.qr],transformed=True)
    return result.filtered_state[0]*fit.scale, result.filtered_state[1]*fit.scale, result.filtered_state_cov[0,0]*fit.scale**2


def manual_filter(spread, fit):
    """Independent two-state recursion used to verify the C-backed filter."""
    mean=np.zeros(2);cov=np.diag([fit.qm/(1-fit.rho**2),1e6])
    trans=np.diag([fit.rho,1.]);q=np.diag([fit.qm,fit.qr]);out=[]
    for i,y in enumerate(np.asarray(spread)/fit.scale):
        if i:
            mean=trans@mean;cov=trans@cov@trans.T+q
        innovation=y-mean.sum();s=cov.sum()+1e-9
        gain=cov@np.ones(2)/s
        mean=mean+gain*innovation
        cov=cov-np.outer(gain,np.ones(2)@cov)
        out.append(mean*fit.scale)
    return np.array(out).T
