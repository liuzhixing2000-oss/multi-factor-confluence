# Multi-factor confluence v0.1

Independent research scanner for Bybit linear USDT instruments. No execution API, no exchange credentials, no profitability claim. Candidate signals appear in Railway logs and GET /signals. No Telegram integration in v0.1.

## Exact feature inventory
10 feature templates × 8 periods (6,9,12,18,24,36,48,72) × 3 timeframes (15m,1h,4h) = **240 features**, not 240 independent indicators.

- Trend: price/SMA, price/EMA, EMA slope.
- Momentum: simple rolling RSI balance, ATR-normalized price change.
- Volume: price/VWAP, volume-weighted close location. These are OHLCV proxies, not actual trade delta/orderflow.
- Structure: prior channel midpoint distance and prior channel breakout.
- Volatility: ATR/price used as an eligibility gate, not a directional vote.

Each directional group averages signed features; grouped score averages four groups equally. This limits category duplication but does not statistically decorrelate features. Candidate: absolute score >=0.55; >=3 groups aligned at >=0.35; agrees with 4h EMA24 direction; 15m ATR24/price between 0.1% and 4%; every feature available. Thresholds are unoptimized research defaults. Votes are NOT win probabilities.

## Live scanner
Default top 30 USDT linear tickers by current 24h turnover, minimum $10m. This can include BTC/ETH; universe is not a historical point-in-time universe. Set SYMBOLS=SOLUSDT,LINKUSDT,... to fix symbols, or TOP_N=30. Fetches 1400 bars/symbol each scan, runs after each 15m boundary. Closed bars only; complete 1h/4h candles only; rejects gaps, insufficient history and stale feed. Does not call orders or send messages. In-memory same-candle dedup resets on restart. Logs have Railway's retention limits; persistent forward trade tracking is not implemented. /health is process liveness, /signals includes scan status/errors.

Railway uses Dockerfile and railway.toml. Start command: `python app.py serve`. No API key needed. Default service has no public domain; inspect private service logs. API access failures are reported explicitly, never replaced by fake data.

## Backtest
```
python -m unittest -v
python app.py backtest --symbol SOLUSDT --bars 10000 --out results
python app.py backtest --csv candles.csv --symbol SOLUSDT --out results
```
CSV index is UTC candle CLOSE timestamp; columns o,h,l,c,v; 15m uninterrupted bars. Last 30% chronological holdout (minimum 1200 warmup bars). Compares grouped, naive feature majority and 4h EMA24 baseline. All use next-bar open, 2 ATR fixed stop, 3R target, 32-bar max holding, one trade per symbol. Stop takes precedence if both touched; gap-through-stop uses adverse open. Fees 6bps/side, slippage 3bps/side, funding stress charge 1bp per 8 hours prorated (not actual funding). CLI outputs trade CSVs and summary JSON. Entry timestamp in CSV denotes the next candle's opening instant.

Limitations: no walk-forward optimization, historical universe/delistings, actual funding, spread/depth modeling, portfolio exposure/correlation constraints, statistical significance or live position lifecycle. Per-trade returns are NOT account returns. Fixed exit is a controlled comparison baseline, not a validated optimal exit. Do not choose the best of these policies on the holdout and still call that holdout unseen. Historical profitability has not been established.

## Verification
Deterministic tests check all 240 features, prefix/future invariance (including incomplete higher timeframes), warmup suppression, next-open entries, adverse same-bar stop/target ordering and costs. Synthetic data tests establish implementation behavior only.
