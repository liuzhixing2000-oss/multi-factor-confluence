"""Causal OHLCV research engine. Scores are votes, never probabilities."""
import numpy as np
import pandas as pd

PERIODS = (6, 9, 12, 18, 24, 36, 48, 72)
GROUPS = ('trend', 'momentum', 'volume', 'structure')

def validate(d):
    if not d.index.is_monotonic_increasing or d.index.has_duplicates:
        raise ValueError('Timestamps must be unique and increasing')
    if d[list('ohlcv')].isna().any().any() or not np.isfinite(d[list('ohlcv')]).all().all():
        raise ValueError('Invalid OHLCV')
    if (d[['o','h','l','c']] <= 0).any().any() or (d.v < 0).any():
        raise ValueError('Invalid prices/volume')
    if ((d.h < d[['o','c','l']].max(axis=1)) | (d.l > d[['o','c','h']].min(axis=1))).any():
        raise ValueError('Invalid candle range')

def features(d):
    validate(d)
    c,h,l,v = d.c,d.h,d.l,d.v
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    delta=c.diff(); out={}
    for n in PERIODS:
        ma=c.rolling(n).mean(); atr=tr.rolling(n).mean().replace(0,np.nan)
        ema=c.ewm(span=n,adjust=False,min_periods=n).mean()
        hi=h.shift().rolling(n).max(); lo=l.shift().rolling(n).min()
        gain=delta.clip(lower=0).rolling(n).mean(); loss=(-delta.clip(upper=0)).rolling(n).mean()
        rsi=(gain-loss)/(gain+loss).replace(0,np.nan)
        vol=v.rolling(n).sum().replace(0,np.nan)
        vw=(c*v).rolling(n).sum()/vol
        clv=((2*c-h-l)/(h-l).replace(0,np.nan)).fillna(0)
        vals={
            'trend.ma':(c-ma)/atr,
            'trend.ema':(c-ema)/atr,
            'trend.slope':(ema-ema.shift(3))/atr,
            'momentum.rsi':rsi,
            'momentum.roc':(c-c.shift(n))/atr,
            'volume.vwap':(c-vw)/atr,
            'volume.clv':(clv*v).rolling(n).sum()/vol,
            'structure.channel':(c-(hi+lo)/2)/atr,
            'structure.breakout':pd.Series(np.where(c>hi,1,np.where(c<lo,-1,0)),index=c.index).where(hi.notna()),
            'volatility.atr_pct':atr/c,
        }
        for k,x in vals.items(): out[f'{k}.{n}']=x
    return pd.DataFrame(out,index=d.index)

def scores(base):
    validate(base)
    if not base.index.to_series().diff().dropna().eq(pd.Timedelta(minutes=15)).all():
        raise ValueError("Expected uninterrupted 15m candles")
    allf=[]
    # Index denotes candle CLOSE time; higher timeframe features exist only at close.
    for label,minutes in [('15m',15),('1h',60),('4h',240)]:
        d=base if minutes==15 else base.resample(f'{minutes}min',closed='right',label='right',origin='epoch').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'})
        if minutes!=15:
            count=base.c.resample(f'{minutes}min',closed='right',label='right',origin='epoch').count()
            d=d[count==minutes//15]
        f=features(d).add_prefix(label+'|').reindex(base.index,method='ffill')
        allf.append(f)
    f=pd.concat(allf,axis=1)
    out=pd.DataFrame(index=base.index)
    for g in GROUPS:
        out[g]=np.sign(f.filter(regex=r'\|'+g+r'\.')).mean(axis=1)
    directional=f.loc[:,~f.columns.str.contains('volatility')]
    out['naive']=np.sign(directional).mean(axis=1)
    out['grouped']=out[list(GROUPS)].mean(axis=1)
    out['baseline']=np.sign(f['4h|trend.ema.24'])
    out['atr_pct']=f['15m|volatility.atr_pct.24']
    out['ready']=f.notna().all(axis=1)
    for policy in ['grouped','naive','baseline']:
        direction=np.sign(out[policy])
        eligible=out.ready & out.atr_pct.between(.001,.04)
        if policy!='baseline': eligible &= out[policy].abs().ge(.55)
        if policy=='grouped':
            eligible &= (out[list(GROUPS)].mul(direction,axis=0)>=.35).sum(axis=1)>=3
            eligible &= direction.eq(out.baseline)
        out[policy+'_signal']=direction.where(eligible,0).astype(int)
    return out,f

def backtest(d,policy='grouped',start=None,fee_bps=6,slippage_bps=3,funding_bps_per_8h=1,max_bars=32):
    s,_=scores(d); records=[]; i=0
    while i<len(d)-1:
        side=int(s.iloc[i][policy+'_signal'])
        if not side or (start is not None and d.index[i]<start): i+=1; continue
        # Signal on closed candle; executable entry at next candle open.
        entry=float(d.o.iloc[i+1])*(1+side*slippage_bps/10000)
        risk=float(d.c.iloc[i]*s.atr_pct.iloc[i]*2)
        stop=entry-side*risk; target=entry+side*3*risk
        end=min(i+max_bars,len(d)-1); reason='time'
        for j in range(i+1,end+1):
            row=d.iloc[j]
            hit_stop=row.l<=stop if side==1 else row.h>=stop
            hit_target=row.h>=target if side==1 else row.l<=target
            if hit_stop:
                raw=min(stop,row.o) if side==1 else max(stop,row.o)
                reason='stop'; break
            if hit_target: raw=target; reason='target'; break
            raw=row.c
        exit_price=raw*(1-side*slippage_bps/10000)
        gross=side*(exit_price-entry)/entry
        fees=fee_bps/10000*(1+exit_price/entry)
        funding=funding_bps_per_8h/10000*((j-i)/32)
        net=gross-fees-funding
        records.append(dict(signal_time=str(d.index[i]),entry_time=str(d.index[i+1]-pd.Timedelta(minutes=15)),exit_time=str(d.index[j]),side=side,entry=entry,exit=exit_price,net_return=net,net_r=net/(risk/entry),reason=reason))
        i=j  # One position per symbol; may signal on the exit candle close.
    return pd.DataFrame(records)
