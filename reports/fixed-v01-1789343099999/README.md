# Fixed v0.1 ETH / BTC / SOL backtest

Source commit: b0d06d320007a769dfde96d105a09099786f8dab
Railway deployment: 0a25b4f9-dde5-45d1-85a7-6f49a63dc2a1

Data: 2025-09-14 00:00 to 2026-09-13 23:45 UTC. Fixed last-30% test starts 2026-05-27 12:00 UTC. 35,040 bars per symbol. No parameters optimized.

|Symbol|Policy|Trades|Win rate|Mean net return|PF|Sum R|Max drawdown R|
|---|---|---:|---:|---:|---:|---:|---:|
|ETHUSDT|grouped|326|30.1%|-0.154%|0.73|-85.30|98.84|
|ETHUSDT|naive|339|28.3%|-0.168%|0.70|-98.75|110.27|
|ETHUSDT|baseline|620|31.0%|-0.160%|0.70|-194.88|211.55|
|BTCUSDT|grouped|333|30.3%|-0.163%|0.65|-116.83|131.57|
|BTCUSDT|naive|355|29.9%|-0.183%|0.61|-131.51|143.92|
|BTCUSDT|baseline|587|31.3%|-0.134%|0.68|-185.06|202.62|
|SOLUSDT|grouped|327|30.6%|-0.148%|0.76|-72.96|85.64|
|SOLUSDT|naive|352|30.4%|-0.142%|0.77|-81.49|97.91|
|SOLUSDT|baseline|606|32.0%|-0.131%|0.78|-137.84|146.38|

All nine policy/symbol combinations lose after assumed costs. Grouped beats naive per-trade return on ETH and BTC, but not SOL. No validated trading edge established.

Costs: fee 6bps/side, slippage 3bps/side, prorated funding stress 1bp/8h (not historical funding). Exits: 2 ATR stop, 3R target, 32 bars maximum; next-open entries; adverse stop priority. R equals each trade initial stop distance. Sum R/drawdown R are sequential per-symbol risk units, not portfolio or account returns.

This is a retrospective chronological test, not a prospective out-of-sample claim: code was written after the historical dates. No account equity simulation, bootstrap significance, historical funding or full-year performance reported. Stored CSVs reproduce summary calculations; source data hashes are in summary.json. Market data were downloaded on Railway; raw bars are not archived.
