import argparse,json,os,time,urllib.request,urllib.parse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from threading import Thread
from pathlib import Path
import pandas as pd
from engine import scores,backtest

API=os.getenv('BYBIT_API','https://api.bybit.com')
STATE={'status':'starting','mode':'research_only','version':'0.1.0'}

def get(path,params):
    url=API+path+'?'+urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=20) as r: data=json.load(r)
            if data.get('retCode')!=0: raise RuntimeError(str(data.get('retMsg')))
            return data['result']
        except Exception:
            if attempt==2: raise
            time.sleep(attempt+1)

def candles(symbol,bars=1400):
    end=int(time.time()*1000); rows=[]
    while len(rows)<bars:
        batch=get('/v5/market/kline',dict(category='linear',symbol=symbol,interval='15',limit=min(1000,bars-len(rows)),end=end))['list']
        if not batch: break
        rows.extend(batch); end=min(int(x[0]) for x in batch)-1
    d=pd.DataFrame(rows,columns=['start','o','h','l','c','v','turnover']).astype(float)
    d['close_time']=pd.to_datetime(d.start+900000,unit='ms',utc=True)
    d=d.set_index('close_time').sort_index(); d=d[~d.index.duplicated()]
    d=d[d.index<=pd.Timestamp.now(tz='UTC')][list('ohlcv')]
    if len(d)<1200: raise ValueError('Insufficient history: need 1200 closed bars')
    if not d.index.to_series().diff().dropna().eq(pd.Timedelta(minutes=15)).all(): raise ValueError('Candle gap')
    return d

def universe():
    specified=os.getenv('SYMBOLS')
    if specified: return specified.split(',')
    tickers=get('/v5/market/tickers',{'category':'linear'})['list']
    eligible=[t for t in tickers if t['symbol'].endswith('USDT') and float(t.get('turnover24h',0))>=10_000_000]
    eligible.sort(key=lambda t:float(t['turnover24h']),reverse=True)
    return [t['symbol'] for t in eligible[:int(os.getenv('TOP_N','30'))]]

def emit(event): print(json.dumps(event,allow_nan=False),flush=True)

def scan(seen):
    results=[]; errors=[]; symbols=universe()
    for symbol in symbols:
        try:
            d=candles(symbol)
            if pd.Timestamp.now(tz='UTC')-d.index[-1]>pd.Timedelta(minutes=20): raise ValueError('Stale candles')
            s,f=scores(d); row=s.iloc[-1]; stamp=str(s.index[-1])
            event={'symbol':symbol,'candle_close':stamp,'price':float(d.c.iloc[-1]),'ready':bool(row.ready),'features':len(f.columns),'groups':{g:round(float(row[g]),3) for g in ['trend','momentum','volume','structure']},'vote_score':round(float(row.grouped),3),'side':int(row.grouped_signal),'research_only':True}
            results.append(event)
            key=symbol+stamp
            if event['side'] and key not in seen:
                event['event']='candidate'; event['reference_stop_distance']=float(d.c.iloc[-1]*row.atr_pct*2)
                emit(event); seen.add(key)
        except Exception as e:
            errors.append({'symbol':symbol,'error':str(e)}); emit({'event':'symbol_error',**errors[-1]})
    STATE.update(status='ok' if results and not errors else 'degraded',updated_at=datetime.now(timezone.utc).isoformat(),results=results,errors=errors)
    emit({'event':'scan_complete','scanned':len(results),'errors':len(errors),'candidates':sum(bool(x['side']) for x in results)})

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ['/health','/signals']: self.send_error(404); return
        payload={'alive':True,'status':STATE['status']} if self.path=='/health' else STATE
        body=json.dumps(payload,allow_nan=False).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(body)
    def log_message(self,*args): pass

def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['serve','scan','backtest']); p.add_argument('--symbol',default='SOLUSDT'); p.add_argument('--bars',type=int,default=10000); p.add_argument('--csv'); p.add_argument('--out',default='results'); args=p.parse_args()
    if args.mode=='backtest':
        d=pd.read_csv(args.csv,index_col=0,parse_dates=True) if args.csv else candles(args.symbol,args.bars)
        if len(d)<1500: raise ValueError('Need >=1500 bars for research split')
        start=d.index[max(1200,int(len(d)*.7))]; Path(args.out).mkdir(parents=True,exist_ok=True)
        summary={}
        for policy in ['grouped','naive','baseline']:
            t=backtest(d,policy,start=start); t.to_csv(f'{args.out}/{policy}_trades.csv',index=False)
            summary[policy]={'trades':len(t),'mean_net_return':float(t.net_return.mean()) if len(t) else None,'win_rate':float((t.net_return>0).mean()) if len(t) else None,'sum_net_r':float(t.net_r.sum()) if len(t) else 0}
        report={'symbol':args.symbol,'test_start':str(start),'summary':summary,'limitations':['Fixed chronological 30% holdout, not walk-forward validation','Fees 6bps/side; slippage 3bps/side; funding stress charge 1bp/8h, not historical funding','Per-symbol trade statistics, not portfolio returns','Current universe has survivorship bias; no profitability claim']}
        Path(args.out,'summary.json').write_text(json.dumps(report,indent=2)); emit(report); return
    if args.mode=='scan': scan(set()); return
    Thread(target=lambda:HTTPServer(('0.0.0.0',int(os.getenv('PORT','8080'))),Handler).serve_forever(),daemon=True).start()
    seen=set()
    emit({'event':'started','version':'0.1.0','features':240,'mode':'research_only'})
    while True:
        try: scan(seen)
        except Exception as e: STATE.update(status='degraded',error=str(e)); emit({'event':'scan_error','error':str(e)})
        if len(seen)>10000: seen.clear()
        time.sleep(max(30,900-time.time()%900+10))

if __name__=='__main__': main()
