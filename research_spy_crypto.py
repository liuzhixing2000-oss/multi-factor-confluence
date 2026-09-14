"""SPY early return -> crypto 15:30-16:00 NY. Exploratory, fixed rules."""
import json, urllib.request, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
def fetch(url):
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
        except Exception:
            if attempt==2: raise
            time.sleep(2)
def run():
    j=fetch("https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1mo&interval=5m")["chart"]["result"][0]
    q=j["indicators"]["quote"][0]; days={}
    for i,t in enumerate(j["timestamp"]):
        dt=datetime.fromtimestamp(t,NY)
        if q["close"][i] is not None:
            days.setdefault(dt.date(),{})[dt.strftime("%H:%M")]=q["close"][i]
    sessions=[]; previous=None
    for day,b in sorted(days.items()):
        if "15:55" not in b: previous=None; continue
        if previous is not None and "09:55" in b:
            sessions.append((day,b["09:55"]/previous-1))
        previous=b["15:55"]
    print(json.dumps({"event":"sessions","count":len(sessions),"source":"Yahoo SPY 5m","note":"exploratory recent month; no OOS; fees 6bps/side plus slippage 3bps/side; funding excluded"}),flush=True)
    for symbol in ["BTCUSDT","ETHUSDT","SOLUSDT"]:
        trades=[]
        for day,signal in sessions:
            start=datetime.combine(day,datetime.min.time(),NY).replace(hour=15,minute=30)
            ms=int(start.timestamp()*1000)
            j=fetch("https://api.bybit.com/v5/market/kline?category=linear&symbol="+symbol+"&interval=5&start="+str(ms)+"&end="+str(ms+1800000-1)+"&limit=10")
            if j.get("retCode")!=0: raise RuntimeError(str(j))
            rows=sorted(j["result"]["list"],key=lambda a:int(a[0]))
            if len(rows)!=6 or int(rows[0][0])!=ms or int(rows[-1][0])!=ms+1500000: continue
            entry=float(rows[0][1]); exit=float(rows[-1][4]); side=1 if signal>0 else -1 if signal<0 else 0
            gross=side*(exit/entry-1)
            cost=.0009*(1+exit/entry) if side else 0
            trades.append({"date":str(day),"spy_signal":signal,"gross":gross,"net":gross-cost,"long_net":exit/entry-1-.0009*(1+exit/entry)})
            time.sleep(.1)
        for mode in ["net","long_net"]:
            vals=[t[mode] for t in trades]; gain=sum(max(v,0) for v in vals); loss=-sum(min(v,0) for v in vals)
            print(json.dumps({"event":"result","symbol":symbol,"mode":mode,"trades":len(vals),"mean_pct":100*sum(vals)/len(vals) if vals else None,"pf":gain/loss if loss else None,"win_rate":sum(v>0 for v in vals)/len(vals) if vals else None,"detail":trades}),flush=True)
    print('{"event":"complete"}',flush=True)
if __name__=="__main__":
    try: run()
    except Exception as e:
        print(json.dumps({"event":"blocked","error":str(e)}),flush=True)
        raise
