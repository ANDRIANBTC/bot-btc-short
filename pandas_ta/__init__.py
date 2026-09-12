import pandas as pd
import numpy as np

def ema(close, length=None, **kwargs):
    span = length if length is not None else 14
    return close.ewm(span=span, adjust=False).mean()

def rsi(close, length=None, **kwargs):
    window = length if length is not None else 14
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def adx(high, low, close, length=None, **kwargs):
    n = length if length is not None else 14
    # Cálculo simplificado y seguro de ADX para evitar errores de compilación
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    pos_di = 100 * pd.Series(pos_dm).rolling(n).mean() / atr
    neg_di = 100 * pd.Series(neg_dm).rolling(n).mean() / atr
    dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di)
    adx_val = dx.rolling(n).mean()
    return pd.DataFrame({f"ADX_{n}": adx_val})

# Extensión para Pandas DataFrame (.ta) por si tu app.py usa df.ta
@pd.api.extensions.register_dataframe_accessor("ta")
class PandasTAAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj
    def ema(self, length=None, **kwargs):
        return ema(self._obj['close'], length=length, **kwargs)
    def rsi(self, length=None, **kwargs):
        return rsi(self._obj['close'], length=length, **kwargs)
    def adx(self, length=None, **kwargs):
        return adx(self._obj['high'], self._obj['low'], self._obj['close'], length=length, **kwargs)
