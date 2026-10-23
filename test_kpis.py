import unittest
import numpy as np
import pandas as pd
from kpis import hac,block_bootstrap,spot_benchmark

class StatisticalChecks(unittest.TestCase):
    def test_hac_matches_direct_bartlett_matrix(self):
        x=np.random.default_rng(3).normal(.001,.02,100)
        lag=7;n=len(x);z=x-x.mean()
        dist=np.abs(np.arange(n)[:,None]-np.arange(n)[None,:])
        weights=np.maximum(1-dist/(lag+1),0)
        variance=float(z@weights@z/n)
        expected=x.mean()/np.sqrt(variance/n)
        self.assertAlmostEqual(hac(x,lag)['hac_t'],expected,places=10)
    def test_full_length_circular_blocks_preserve_the_mean(self):
        x=np.random.default_rng(4).normal(.001,.02,100)
        b=block_bootstrap(x,100,reps=1000)
        self.assertAlmostEqual(b['mean_ci_low'],x.mean()*365.25,places=10)
        self.assertAlmostEqual(b['mean_ci_high'],x.mean()*365.25,places=10)
    def test_later_spot_prices_cannot_change_earlier_momentum_equity(self):
        h=pd.date_range('2024-01-01',periods=24*70,freq='h',tz='UTC')
        p=pd.DataFrame({'open':100+np.arange(len(h))*.01},index=h)
        grid=pd.date_range('2024-02-01 01:00',periods=20,freq='D',tz='UTC')
        before,_=spot_benchmark(p,grid,'momentum20')
        changed=p.copy();changed.loc[changed.index>=grid[10],'open']*=2
        after,_=spot_benchmark(changed,grid,'momentum20')
        self.assertTrue(np.allclose(before[:10],after[:10]))

if __name__=='__main__':unittest.main()
