"""Frozen pullback hypotheses. No parameter search."""
import numpy as np
from engine import scores,backtest as base_backtest

def pullback_scores(d):
    s,f=scores(d)
    up=(f['4h|trend.ema.24']>0)&(f['4h|trend.slope.24']>0)&(f['1h|trend.ema.24']>0)&(f['1h|trend.slope.24']>0)
    down=(f['4h|trend.ema.24']<0)&(f['4h|trend.slope.24']<0)&(f['1h|trend.ema.24']<0)&(f['1h|trend.slope.24']<0)
    # EMA24 on closed 15m candles. First countertrend close starts a pullback.
    x=f['15m|trend.ema.24']
    long_touch=up & (x<=0) & (x.shift(1)>0)
    short_touch=down & (x>=0) & (x.shift(1)<0)
    long_recent=long_touch.shift(1).rolling(8,min_periods=1).max().eq(1)
    short_recent=short_touch.shift(1).rolling(8,min_periods=1).max().eq(1)
    long_resume=up & long_recent & (x>0)&(x.shift(1)<=0)
    short_resume=down & short_recent & (x<0)&(x.shift(1)>=0)
    eligible=s.ready & s.atr_pct.between(.001,.04)
    body=(d.c-d.o).abs(); rng=(d.h-d.l).replace(0,np.nan)
    lower=d[['o','c']].min(axis=1)-d.l; upper=d.h-d[['o','c']].max(axis=1)
    bull_pin=(lower>=2*body)&(lower>=upper)&((d.c-d.l)/rng>=.60)&(d.c>d.o)
    bear_pin=(upper>=2*body)&(upper>=lower)&((d.h-d.c)/rng>=.60)&(d.c<d.o)
    long_pin=up & long_recent & bull_pin
    short_pin=down & short_recent & bear_pin
    # 4H-only direction: no 1H trend filter, but still require a post-pullback rejection candle.
    htf_up=(f['4h|trend.ema.24']>0)
    htf_down=(f['4h|trend.ema.24']<0)
    htf_long_recent=((htf_up & (x<=0) & (x.shift(1)>0)).shift(1).rolling(8,min_periods=1).max().eq(1))
    htf_short_recent=((htf_down & (x>=0) & (x.shift(1)<0)).shift(1).rolling(8,min_periods=1).max().eq(1))
    htf_long_pin=htf_up & htf_long_recent & bull_pin
    htf_short_pin=htf_down & htf_short_recent & bear_pin
    for name,long,short in [('pullback_touch',long_touch,short_touch),('pullback_resume',long_resume,short_resume),('pullback_pinbar',long_pin,short_pin),('htf_pinbar',htf_long_pin,htf_short_pin)]:
        s[name+'_signal']=np.where(eligible&long,1,np.where(eligible&short,-1,0))
    return s

def backtest(d,policy='grouped',signal_frame=None,**kwargs):
    return base_backtest(d,policy,signal_frame=(pullback_scores(d) if signal_frame is None else signal_frame),**kwargs)

def macd_fib_scores(d):
    s,f=scores(d)
    def macd(x):
        e12=x.ewm(span=12,adjust=False,min_periods=12).mean(); e26=x.ewm(span=26,adjust=False,min_periods=26).mean(); line=e12-e26; sig=line.ewm(span=9,adjust=False,min_periods=9).mean(); return line-sig
    # Causal divergence proxy: trend has advanced while MACD histogram has weakened over lookback.
    h4=macd(d.resample('240min',closed='right',label='right',origin='epoch').c.last()).reindex(d.index,method='ffill')
    h1=macd(d.resample('60min',closed='right',label='right',origin='epoch').c.last()).reindex(d.index,method='ffill')
    px=d.c; look=24
    bear=(px.pct_change(look)>0.015)&(h4.diff(look)<0)&(h1.diff(look)<0)
    bull=(px.pct_change(look)<-0.015)&(h4.diff(look)>0)&(h1.diff(look)>0)
    late=bear|bull
    hi=d.h.shift(1).rolling(96).max(); lo=d.l.shift(1).rolling(96).min(); span=hi-lo
    fib_long=hi-span*.618; fib_short=hi-span*.382
    up=(f['4h|trend.ema.24']>0)&(f['4h|trend.slope.24']>0)&(f['1h|trend.ema.24']>0)&(f['1h|trend.slope.24']>0)
    down=(f['4h|trend.ema.24']<0)&(f['4h|trend.slope.24']<0)&(f['1h|trend.ema.24']<0)&(f['1h|trend.slope.24']<0)
    # enter while price is inside the 0.382-0.618 retracement zone; use rejection candle to avoid blind limit.
    body=(d.c-d.o).abs(); rng=(d.h-d.l).replace(0,np.nan); lower=d[['o','c']].min(axis=1)-d.l; upper=d.h-d[['o','c']].max(axis=1)
    bull_pin=(lower>=2*body)&(lower>=upper)&((d.c-d.l)/rng>=.60)&(d.c>d.o)
    bear_pin=(upper>=2*body)&(upper>=lower)&((d.h-d.c)/rng>=.60)&(d.c<d.o)
    zone_long=(d.c.between(fib_long,fib_short))&bull_pin
    zone_short=(d.c.between(fib_long,fib_short))&bear_pin
    eligible=s.ready&s.atr_pct.between(.001,.04)
    s['macd_bear_div']=bear; s['macd_bull_div']=bull; s['fib_zone_long']=zone_long; s['fib_zone_short']=zone_short
    s['macd_fib_filter_signal']=np.where(eligible&up&zone_long&~late,1,np.where(eligible&down&zone_short&~late,-1,0))
    # Countertrend reversal only on divergence plus opposite rejection candle in fib zone.
    s['macd_fib_reversal_signal']=np.where(eligible&bear&zone_short, -1, np.where(eligible&bull&zone_long,1,0))
    return s

def bb_div_scores(d):
    s,f=scores(d)
    def macd(x):
        line=x.ewm(span=12,adjust=False,min_periods=12).mean()-x.ewm(span=26,adjust=False,min_periods=26).mean(); return line-line.ewm(span=9,adjust=False,min_periods=9).mean()
    c4=d.resample('240min',closed='right',label='right',origin='epoch').c.last(); c1=d.resample('60min',closed='right',label='right',origin='epoch').c.last()
    h4=macd(c4).reindex(d.index,method='ffill'); h1=macd(c1).reindex(d.index,method='ffill'); px=d.c; look=24
    bear=(px.pct_change(look)>0.015)&(h4.diff(look)<0)&(h1.diff(look)<0); bull=(px.pct_change(look)<-0.015)&(h4.diff(look)>0)&(h1.diff(look)>0)
    ma=c4.rolling(20).mean(); sd=c4.rolling(20).std(); upper=(ma+2*sd).reindex(d.index,method='ffill'); lower=(ma-2*sd).reindex(d.index,method='ffill')
    touch_up=(px>=upper*.995); touch_down=(px<=lower*1.005)
    eligible=s.ready&s.atr_pct.between(.001,.04)
    s['bb_div_reversal_signal']=np.where(eligible&bull&touch_down,1,np.where(eligible&bear&touch_up,-1,0))
    up=(f['4h|trend.ema.24']>0)&(f['1h|trend.ema.24']>0); down=(f['4h|trend.ema.24']<0)&(f['1h|trend.ema.24']<0)
    s['bb_div_filter_signal']=np.where(eligible&up&~bear&touch_down,1,np.where(eligible&down&~bull&touch_up,-1,0))
    return s
