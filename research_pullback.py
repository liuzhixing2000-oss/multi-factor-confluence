"""One-shot fixed-parameter three-symbol study; scanner runs alongside it."""
import base64,gzip,hashlib,json,sys,time,traceback
from pathlib import Path
from threading import Thread
import numpy as np
import pandas as pd
from app import get,emit,main
from pullback import backtest

def download(symbol,end,bars=35040):
    rows=[]; cursor=end
    while len(rows)<bars:
        b=get('/v5/market/kline',dict(category='linear',symbol=symbol,interval='15',limit=min(1000,bars-len(rows)),end=cursor))['list']
        if not b: raise RuntimeError('Incomplete history')
        rows.extend(b); cursor=min(int(x[0]) for x in b)-1
        time.sleep(.12)
    d=pd.DataFrame(rows,columns=['start','o','h','l','c','v','turnover']).astype(float)
    d['close_time']=pd.to_datetime(d.start+900000,unit='ms',utc=True)
    d=d.set_index('close_time').sort_index()[list('ohlcv')]
    if d.index.has_duplicates or not d.index.to_series().diff().dropna().eq(pd.Timedelta(minutes=15)).all(): raise ValueError('Duplicate or missing candles')
    return d

def metrics(t):
    if t.empty: return {'trades':0}
    x=t.net_r.to_numpy(); ret=t.net_return.to_numpy(); eq=np.r_[0,np.cumsum(x)]
    return {'trades':len(t),'win_rate':float((x>0).mean()),'mean_net_return':float(ret.mean()),'mean_net_r':float(x.mean()),'sum_net_r':float(x.sum()),'profit_factor':float(ret[ret>0].sum()/-ret[ret<0].sum()) if (ret<0).any() else None,'max_drawdown_r':float(np.max(np.maximum.accumulate(eq)-eq)),'long_trades':int((t.side==1).sum()),'short_trades':int((t.side==-1).sum()),'exit_counts':t.reason.value_counts().to_dict()}

def run():
    try:
        end=1789343099999
        report={'run_id':f'pullback-v01-{end}','end_request_ms':end,'bars_per_symbol':35040,'test_fraction':.3,'source':'Bybit linear USDT 15m','costs':{'fee_bps_per_side':6,'slippage_bps_per_side':3,'funding_stress_bps_per_8h':1},'results':{}}
        archive={}; emit({'event':'research_started','run_id':report['run_id']})
        for symbol in ['ETHUSDT','BTCUSDT','SOLUSDT']:
            d=download(symbol,end); start=d.index[int(len(d)*.7)]
            item={'data_start':str(d.index[0]),'data_end':str(d.index[-1]),'test_start':str(start),'data_sha256':hashlib.sha256(d.to_csv().encode()).hexdigest(),'policies':{}}
            emit({'event':'research_data_ready','symbol':symbol,'bars':len(d)})
            for policy in ['grouped','pullback_pinbar','htf_pinbar']:
                t=backtest(d,policy,start=start)
                item['policies'][policy]=metrics(t)
                item['policies'][policy]['months']={m:metrics(g) for m,g in t.groupby(pd.to_datetime(t.signal_time,utc=True).dt.strftime('%Y-%m'))} if len(t) else {}
                archive[f'{symbol}_{policy}_trades.csv']=t.to_csv(index=False)
                emit({'event':'research_result','symbol':symbol,'policy':policy,**metrics(t)})
            report['results'][symbol]=item
        archive['summary.json']=json.dumps(report,indent=2)
        payload=base64.b64encode(gzip.compress(json.dumps(archive).encode())).decode()
        chunks=[payload[i:i+2500] for i in range(0,len(payload),2500)]
        for i,chunk in enumerate(chunks):
            emit({'event':'research_archive','run_id':report['run_id'],'part':i,'total':len(chunks),'data':chunk}); time.sleep(.03)
        emit({'event':'research_complete','run_id':report['run_id'],'archive_sha256':hashlib.sha256(payload.encode()).hexdigest(),'parts':len(chunks)})
    except Exception:
        emit({'event':'research_failed','error':traceback.format_exc()})

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='serve':
        Thread(target=run,daemon=True).start(); main()
    else: run()
