import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import requests
import os

# Configuración de la página
st.set_page_config(
    page_title="Bot Cuantitativo BTC/USDT (Long & Short)",
    page_icon="📈",
    layout="centered"
)

# Cargar credenciales desde secrets de Streamlit Cloud o variables de entorno
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))

def enviar_alerta_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=300)
def cargar_y_analizar_datos():
    exchange = ccxt.kraken()
    bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='4h', limit=300)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    
    # 1. EMA
    df['ema20'] = close.ewm(span=20, adjust=False).mean()
    df['ema50'] = close.ewm(span=50, adjust=False).mean()
    
    # 2. RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. ADX y Direcionales
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()
    
    plus_dm = high.diff()
    minus_dm = low.shift() - low
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    
    df['plus_di'] = 100 * pd.Series(plus_dm).rolling(window=14).mean() / atr
    df['minus_di'] = 100 * pd.Series(minus_dm).rolling(window=14).mean() / atr
    
    dx = 100 * (df['plus_di'] - df['minus_di']).abs() / (df['plus_di'] + df['minus_di']).abs()
    df['adx'] = dx.rolling(window=14).mean()
    
    return df.dropna().reset_index(drop=True)

# Título de la App
st.title("📈 Bot Cuantitativo BTC/USDT (Long & Short)")
st.markdown("Panel de control en tiempo real con sistema de alertas automatizadas (Temporalidad 4h).")

# Botón de prueba a Telegram
if st.button("📢 Enviar Alerta de Prueba a Telegram"):
    exito = enviar_alerta_telegram("🔔 *Prueba de conexión exitosa* desde el Bot Cuantitativo BTC/USDT.")
    if exito:
        st.success("¡Alerta de prueba enviada con éxito a Telegram!")
    else:
        st.error("Error al enviar. Verifica tus credenciales de Telegram en los Secrets.")

try:
    df = cargar_y_analizar_datos()
    ultima_vela = df.iloc[-1]
    penultima_vela = df.iloc[-2]

    precio_actual = float(ultima_vela['close'])
    ema20 = float(ultima_vela['ema20'])
    ema50 = float(ultima_vela['ema50'])
    rsi = float(ultima_vela['rsi'])
    rsi_prev = float(penultima_vela['rsi'])
    adx = float(ultima_vela['adx'])
    plus_di = float(ultima_vela['plus_di'])
    minus_di = float(ultima_vela['minus_di'])

    threshold = 78.0
    sl_pct = 0.015
    tp_pct = 0.030

    # Evaluación Short
    score_short = 0.0
    if precio_actual < ema20 and ema20 < ema50: score_short += 25.0
    if ema20 < ema50: score_short += 15.0
    if (rsi > 65) or (35 <= rsi <= 50): score_short += 15.0
    if rsi < rsi_prev: score_short += 10.0
    if adx > 25: score_short += 15.0
    if minus_di > plus_di: score_short += 20.0

    # Evaluación Long
    score_long = 0.0
    if precio_actual > ema20 and ema20 > ema50: score_long += 25.0
    if ema20 > ema50: score_long += 15.0
    if (rsi < 35) or (50 <= rsi <= 65): score_long += 15.0
    if rsi > rsi_prev: score_long += 10.0
    if adx > 25: score_long += 15.0
    if plus_di > minus_di: score_long += 20.0

    # Métricas visuales en columnas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio BTC/USDT", f"${precio_actual:,.2f}")
    col2.metric("RSI Actual", f"{rsi:.1f}")
    col3.metric("Puntuación Long", f"{score_long:.1f} / {threshold}")
    col4.metric("Puntuación Short", f"{score_short:.1f} / {threshold}")

    st.markdown("---")
    st.subheader("Estado de la Señal (Temporalidad 4h)")

    if score_short >= threshold:
        sl_precio = precio_actual * (1.0 + sl_pct)
        tp_precio = precio_actual * (1.0 - tp_pct)
        st.error(f"🚨 **¡SEÑAL SHORT ACTIVADA!** Score: {score_short:.1f} / {threshold}\n\n"
                 f"- **Entrada:** ${precio_actual:,.2f}\n"
                 f"- **Stop Loss (1.5%):** ${sl_precio:,.2f}\n"
                 f"- **Take Profit (3.0%):** ${tp_precio:,.2f}")
    elif score_long >= threshold:
        sl_precio = precio_actual * (1.0 - sl_pct)
        tp_precio = precio_actual * (1.0 + tp_pct)
        st.success(f"🟢 **¡SEÑAL LONG ACTIVADA!** Score: {score_long:.1f} / {threshold}\n\n"
                   f"- **Entrada:** ${precio_actual:,.2f}\n"
                   f"- **Stop Loss (1.5%):** ${sl_precio:,.2f}\n"
                   f"- **Take Profit (3.0%):** ${tp_precio:,.2f}")
    else:
        st.info(f"⏳ **ESTADO: WAIT** (Sin confluencia suficiente. Long: {score_long:.1f} | Short: {score_short:.1f})")

    with st.expander("📊 Ver métricas técnicas detalladas"):
        st.write(f"- **EMA 20:** ${ema20:,.2f}")
        st.write(f"- **EMA 50:** ${ema50:,.2f}")
        st.write(f"- **ADX:** {adx:.1f}")
        st.write(f"- **+DI:** {plus_di:.1f} | **-DI:** {minus_di:.1f}")
        st.write(f"- **RSI Anterior:** {rsi_prev:.1f}")

except Exception as e:
    st.error(f"⚠️ Error al conectar con Kraken o procesar datos: {e}")

if st.button("Actualizar Datos de Mercado"):
    st.cache_data.clear()
    st.rerun()
