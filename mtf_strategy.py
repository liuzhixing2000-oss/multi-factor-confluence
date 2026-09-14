"""Multi-timeframe area -> reaction -> 5m entry research prototype.

All signals are evaluated on closed candles and executed on the next candle open.
"""
import numpy as np
import pandas as pd

def pinbar(d):
    body=(d.c-d.o).abs(); rng=(d.h-d.l).replace(0,np.nan)
    lo=d[['o','c']].min(axis=1)-d.l; hi=d.h-d[['o','c']].max(axis=1)
    return ((lo>=2*body)&(lo>=hi)&((d.c-d.l)/rng>=.6)&(d.c>d.o),
            (hi>=2*body)&(hi>=lo)&((d.h-d.c)/rng>=.6)&(d.c<d.o))

def hourly_zones(h):
    """Causal zones from closed 1h candles: EMA trend, BB, fib and swings."""
    c,hig,lo=h.c,h.h,h.l
    ema20=c.ewm(span=20,adjust=False,min_periods=20).mean()
    ema50=c.ewm(span=50,adjust=False,min_periods=50).mean()
    mid=c.rolling(20).mean(); sd=c.rolling(20).std()
    swing_hi=hig.shift(1).rolling(48).max(); swing_lo=lo.shift(1).rolling(48).min()
    span=swing_hi-swing_lo
    fib382=swing_hi-span*.382; fib618=swing_hi-span*.618
    out=pd.DataFrame(index=h.index)
    out['trend']=np.sign(ema20-ema50)
    out['support']=pd.concat([fib618,mid-2*sd,swing_lo],axis=1).median(axis=1)
    out['resistance']=pd.concat([fib382,mid+2*sd,swing_hi],axis=1).median(axis=1)
    out['width']=(swing_hi-swing_lo)*.08
    return out

def signals(one_h, fifteen_m, five_m):
    z=hourly_zones(one_h).reindex(fifteen_m.index,method='ffill')
    close=fifteen_m.c
    zone_long=(close-z.support).abs()<=z.width
    zone_short=(close-z.resistance).abs()<=z.width
    bull,bear=pinbar(fifteen_m)
    reaction_long=zone_long & bull
    reaction_short=zone_short & bear
    rlong=reaction_long.reindex(five_m.index,method='ffill')
    rshort=reaction_short.reindex(five_m.index,method='ffill')
    b5,s5=pinbar(five_m)
    direction=z.trend.reindex(five_m.index,method='ffill')
    out=pd.DataFrame(index=five_m.index)
    out['long_signal']=(direction>0)&rlong&b5
    out['short_signal']=(direction<0)&rshort&s5
    out['zone_support']=z.support.reindex(five_m.index,method='ffill')
    out['zone_resistance']=z.resistance.reindex(five_m.index,method='ffill')
    return out

def causal_check(one_h,fifteen_m,five_m):
    full=signals(one_h,fifteen_m,five_m)
    for n in (len(five_m)//3,len(five_m)//2):
        part=signals(one_h[one_h.index<=five_m.index[n]],
                     fifteen_m[fifteen_m.index<=five_m.index[n]],
                     five_m.iloc[:n])
        pd.testing.assert_frame_equal(full.iloc[:n],part,recheck_freq=False)
    return True
