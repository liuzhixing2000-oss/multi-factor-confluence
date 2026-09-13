import unittest
import pandas as pd
from test_engine import fixture
from pullback import pullback_scores
class PullbackTests(unittest.TestCase):
    def test_causality(self):
        d=fixture(); s=pullback_scores(d)
        for n in [1250,1263,1296]: pd.testing.assert_frame_equal(s.iloc[:n],pullback_scores(d.iloc[:n]))
    def test_trigger_reclaim(self):
        d=fixture(); s=pullback_scores(d)
        ema=d.c.ewm(span=24,adjust=False,min_periods=24).mean()
        for side in [1,-1]:
            mask=s.pullback_resume_signal.eq(side)
            self.assertTrue((((d.c-ema)*side>0)&((d.c.shift()-ema.shift())*side<=0))[mask].all())
        self.assertTrue(s.loc[~s.ready,'pullback_touch_signal'].eq(0).all())
if __name__=='__main__': unittest.main()
