import numpy as np
import pandas as pd
# imports removed

my_indicator_name = "4H+15M+5M MSS+FVG"
my_indicator_description = "4H定趋势+15M MSS+5M FVG入场,移动止盈(自动补数据)"

def my_indicator(df, params):
    # 自动补历史数据
    symbol = params.get('symbol', '')
    _extra = _load_prefetch(symbol) if len(df) < 2000 and symbol else None
    if _extra is not None and len(_extra) > len(df):
        df = pd.concat([_extra, df])
        df = df[~df.index.duplicated(keep='last')].sort_index()
        df = df.iloc[-3000:]

# @strategy stopLossPct 10
# @strategy takeProfitPct 0
# @strategy trailingEnabled true
# @strategy trailingStopPct 1.5
# @strategy trailingActivationPct 3.6
# @strategy tradeDirection both
# @strategy entryPct 1.0

# @param mss_period int 10
# @param require_fvg bool true

mss_period = int(params.get("mss_period", 10))
require_fvg = str(params.get("require_fvg", "true")).lower() in ("true", "1", "yes")

df = df.copy()
close = df["close"].astype(float)
high = df["high"].astype(float)
low = df["low"].astype(float)
n = len(df)

# ===== 4H 趋势 =====
_trend_bull = False; _trend_bear = False
try:
    if hasattr(df.index, 'date'):
        _4h = df.resample('4h').agg({'close':'last'})
        _c4 = _4h['close'].astype(float)
        _trend_bull = bool(_c4.ewm(span=50,adjust=False).mean().iloc[-1] > _c4.ewm(span=200,adjust=False).mean().iloc[-1])
        _trend_bear = not _trend_bull
except:
    e50 = close.ewm(span=50,adjust=False).mean()
    e200 = close.ewm(span=200,adjust=False).mean()
    _trend_bull = bool(e50.iloc[-1] > e200.iloc[-1])
    _trend_bear = not _trend_bull

# ===== 15M MSS（重采样计算，映射回5M）=====
_mss_bull_5m = pd.Series(False, index=df.index)
_mss_bear_5m = pd.Series(False, index=df.index)
try:
    if hasattr(df.index, 'date'):
        _15m = df.resample('15min').agg({'high':'max','low':'min','close':'last'})
        _h15 = _15m['high'].astype(float); _l15 = _15m['low'].astype(float); _c15 = _15m['close'].astype(float)
        _bull15 = _c15 > _h15.rolling(mss_period).max().shift(1)
        _bear15 = _c15 < _l15.rolling(mss_period).min().shift(1)
        # 将15M信号映射回5M（每根15M包含3根5M）
        for i in range(len(_15m)):
            t_start = _15m.index[i]
            t_end = t_start + pd.Timedelta(minutes=15)
            mask = (df.index >= t_start) & (df.index < t_end)
            _mss_bull_5m.loc[mask] = _bull15.iloc[i] if i < len(_bull15) else False
            _mss_bear_5m.loc[mask] = _bear15.iloc[i] if i < len(_bear15) else False
except:
    pass

# ===== 5M FVG =====
bull_fvg_5m = low > high.shift(2)
bear_fvg_5m = high < low.shift(2)
_fvg_bull = bull_fvg_5m.rolling(10,min_periods=1).max().fillna(False).astype(bool) if require_fvg else pd.Series([True]*n,index=df.index)
_fvg_bear = bear_fvg_5m.rolling(10,min_periods=1).max().fillna(False).astype(bool) if require_fvg else pd.Series([True]*n,index=df.index)

# ===== 信号 =====
trend_bull_s = pd.Series(_trend_bull, index=df.index)
trend_bear_s = pd.Series(_trend_bear, index=df.index)

buy_raw = (trend_bull_s & _mss_bull_5m & _fvg_bull).tolist()
sell_raw = (trend_bear_s & _mss_bear_5m & _fvg_bear).tolist()
buy = [False]*n; sell = [False]*n
add_long = [False]*n; add_short = [False]*n
cl = [False]*n; cs = [False]*n

# 已有持仓时加仓，无持仓时开仓
ip = params.get('initial_position', 0)
for i in range(n):
    if buy_raw[i]:
        if ip > 0: add_long[i] = True
        else: buy[i] = True
    if sell_raw[i]:
        if ip < 0: add_short[i] = True
        else: sell[i] = True

df["buy"]=buy; df["sell"]=sell
df["add_long"]=add_long; df["add_short"]=add_short
df["open_long"]=buy; df["open_short"]=sell
df["close_long"]=cl; df["close_short"]=cs

bm=[None]*n; sm=[None]*n; em=[None]*n; cm=[None]*n

output={"name":my_indicator_name,"plots":[],"signals":[
    {"type":"buy","text":"做多","data":bm,"color":"#00E676"},
    {"type":"sell","text":"做空","data":sm,"color":"#FF1744"},
    {"type":"sell","text":"平多","data":em,"color":"#FFC107"},
    {"type":"buy","text":"平空","data":cm,"color":"#00BCD4"},
]}
