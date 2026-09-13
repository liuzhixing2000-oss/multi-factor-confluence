import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from engine import scores,backtest

def fixture(n=1700):
    rng=np.random.default_rng(42); c=100*np.exp(np.cumsum(rng.normal(.0002,.004,n))); o=np.r_[c[0],c[:-1]]
    return pd.DataFrame({'o':o,'h':np.maximum(o,c)*1.003,'l':np.minimum(o,c)*.997,'c':c,'v':rng.uniform(1,20,n)},index=pd.date_range('2025-01-01 00:15',periods=n,freq='15min',tz='UTC'))

class Tests(unittest.TestCase):
    def test_prefix_invariance(self):
        d=fixture(); full,features=scores(d)
        self.assertEqual(features.shape[1],240)
        self.assertTrue(full.ready.iloc[-1])
        for cut in [1250,1263,1296]:
            short,f=scores(d.iloc[:cut])
            pd.testing.assert_frame_equal(features.iloc[:cut],f)
            pd.testing.assert_frame_equal(full.iloc[:cut],short)
    def test_future_mutation(self):
        d=fixture(); original,_=scores(d); d.iloc[1300:,0:4]*=2
        changed,_=scores(d)
        pd.testing.assert_frame_equal(original.iloc[:1300],changed.iloc[:1300])
    def test_stop_priority_next_open_costs(self):
        d=fixture(5); d.loc[:,:]=[100,110,90,100,10]
        s=pd.DataFrame({'grouped_signal':[1,0,0,0,0],'atr_pct':[.01]*5},index=d.index)
        with patch('engine.scores',return_value=(s,None)):
            t=backtest(d,fee_bps=6,slippage_bps=0)
        self.assertEqual(len(t),1); self.assertEqual(t.reason.iloc[0],'stop')
        self.assertEqual(t.entry_time.iloc[0],str(d.index[0])); self.assertLess(t.net_return.iloc[0],-.02)
    def test_gap_stop(self):
        d=fixture(5); d.loc[:,:]=[100,101,99,100,10]; d.iloc[1]=[95,96,90,94,10]
        s=pd.DataFrame({'grouped_signal':[1,0,0,0,0],'atr_pct':[.01]*5},index=d.index)
        with patch('engine.scores',return_value=(s,None)): t=backtest(d,slippage_bps=0)
        self.assertEqual(t.entry.iloc[0],95); self.assertEqual(t.exit.iloc[0],93)
    def test_no_warmup_signals(self):
        s,_=scores(fixture()); self.assertTrue((s.loc[~s.ready,'grouped_signal']==0).all())

if __name__=='__main__': unittest.main()
