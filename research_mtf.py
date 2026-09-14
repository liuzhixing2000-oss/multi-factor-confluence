import time,json,traceback
import pandas as pd
from app import get,emit
from mtf_strategy import signals,causal_check

def candles(symbol,bars=35040):
 rows=[]; end=int(time.time()*1000)
 while len(rows)<bars:
  b=get('/v5/market/kline',{'category':'linear','symbol':symbol,'interval':'5','limit':min(1000,bars-len(rows)),'end':end})['list']; rows+=b; end=min(int(x[0]) for x in b)-1; time.sleep(.1)
 d=pd.DataFrame(rows,columns=['start','o','h','l','c','v','turn']).astype(float); d.index=pd.to_datetime(d.start+300000,unit='ms',utc=True); return d.sort_index()[list('ohlcv')]
def run():
 try:
  for symbol in ['ETHUSDT','BTCUSDT','SOLUSDT']:
   x=candles(symbol); m=x.resample('15min',closed='right',label='right').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'}).dropna(); h=x.resample('60min',closed='right',label='right').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'}).dropna(); s=signals(h,m,x); causal_check(h,m,x); emit({'event':'mtf_result','symbol':symbol,'bars_5m':len(x),'signals':int((s.long_signal|s.short_signal).sum()),'longs':int(s.long_signal.sum()),'shorts':int(s.short_signal.sum()),'causal_check':True})
  emit({'event':'mtf_complete'})
 except Exception: emit({'event':'mtf_failed','error':traceback.format_exc()})
if __name__=='__main__': run()
