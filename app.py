import streamlit as st
import ccxt
import pandas as pd
import requests
import numpy as np

# Configuración de la página
st.set_page_config(page_title="Crypto Quant Bot - Short Only", page_icon="📉", layout="centered")

st.title("📉 Bot Cuantitativo BTC/USDT (Short-Only)")
st.markdown("Panel de control en tiempo real con sistema de alertas automatizadas.")

# Configuración de Telegram en la pantalla principal
with st.expander("⚙️ Configurar Alertas de Telegram", expanded=True):
    st.markdown("Introduce tus credenciales para activar las notificaciones push en tiempo real.")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        telegram_token = st.text_input("Telegram Bot Token", type="password")
    with col_t2:
        chat_id = st.text_input("Telegram Chat ID", type="password")

def enviar_alerta_telegram(token, chat_id, mensaje):
    """Función para enviar mensajes automáticos vía Telegram"""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Error enviando alerta: {e}")
        return False

# Botón de prueba rápida para verificar Telegram
if st.button("🧪 Enviar Alerta de Prueba a Telegram"):
    if telegram_token and chat_id:
        mensaje_prueba = "🤖 *¡Prueba exitosa!* Tu bot cuantitativo de BTC/USDT está conectado correctamente."
        exito_prueba = enviar_alerta_telegram(telegram_token, chat_id, mensaje_prueba)
        if exito_prueba:
            st.success("¡Mensaje de prueba enviado! Revisa tu Telegram.")
        else:
            st.error("Error al enviar. Revisa que tu Token y tu Chat ID sean correctos.")
    else:
        st.warning("Por favor, introduce primero tu Telegram Bot Token y Chat ID arriba.")

@st.cache_data(ttl=300)
def cargar_datos():
    exchange = ccxt.kraken()
    bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='4h', limit=300)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # Limpiar índices para evitar desalineaciones en los cálculos
    high = df['high'].astype(float).reset_index(drop=True)
    low = df['low'].astype(float).reset_index(drop=True)
    close = df['close'].astype(float).reset_index(drop=True)
    
    # Indicadores técnicos básicos
    df['ema20'] = ta.ema(close, length=20)
    df['ema50'] = ta.ema(close, length=50)
    df['rsi'] = ta.rsi(close, length=14)
    
    # Cálculo seguro de ADX
    adx_df = ta.adx(high, low, close, length=14)
    
    if adx_df is not None and not adx_df.empty and adx_df.shape[1] >= 3:
        df['adx'] = adx_df.iloc[:, 0].values
        df['plus_di'] = adx_df.iloc[:, 1].values
        df['minus_di'] = adx_df.iloc[:, 2].values
    else:
        # Valores por defecto en caso de fallo extremo del indicador
        df['adx'] = 0.0
        df['plus_di'] = 0.0
        df['minus_di'] = 0.0
    
    return df.dropna().reset_index(drop=True)
with st.spinner("Conectando con Binance y calculando indicadores..."):
    df = cargar_datos()

# Datos de la última vela
ultima_vela = df.iloc[-1]
penultima_vela = df.iloc[-2]

precio_actual = float(ultima_vela['close'])
ema20 = float(ultima_vela['ema20'])
ema50 = float(ultima_vela['ema50'])
rsi = float(ultima_vela['rsi'])
rsi_prev = float(penultima_vela['rsi'])
adx = float(ultima_vela['adx'])
minus_di = float(ultima_vela['minus_di'])
plus_di = float(ultima_vela['plus_di'])

# Parámetros del sistema
threshold = 78.0
sl_pct = 0.015
tp_pct = 0.030

# Evaluación de la señal SHORT
score_short = 0.0
if precio_actual < ema20 and ema20 < ema50: score_short += 25.0
if ema20 < ema50: score_short += 15.0
if (rsi > 65) or (35 <= rsi <= 50): score_short += 15.0
if rsi < rsi_prev: score_short += 10.0
if adx > 25: score_short += 15.0
if minus_di > plus_di: score_short += 20.0

# Métricas visuales
col1, col2, col3 = st.columns(3)
col1.metric("Precio BTC/USDT", f"${precio_actual:,.2f}")
col2.metric("RSI Actual", f"{rsi:.1f}")
col3.metric("Puntuación Short", f"{score_short:.1f} / {threshold}")

st.divider()

# Panel de Señal en Tiempo Real
st.subheader("Estado de la Señal (Temporalidad 4h)")

if score_short >= threshold:
    st.error(f"🔴 ¡SEÑAL DE VENTA (SHORT DETECTADA)! Score: {score_short}")
    
    sl_precio = precio_actual * (1.0 + sl_pct)
    tp_precio = precio_actual * (1.0 - tp_pct)
    
    st.markdown(f"""
    * **Precio de Entrada Sugerido:** ${precio_actual:,.2f}
    * **Stop Loss (1.5%):** ${sl_precio:,.2f}
    * **Take Profit (3.0% - Ratio 1:2):** ${tp_precio:,.2f}
    """)
    
    # Disparar alerta automática a Telegram
    if "ultima_alerta_enviada" not in st.session_state:
        st.session_state.ultima_alerta_enviada = None

    identificador_vela = str(ultima_vela['timestamp'])
    if st.session_state.ultima_alerta_enviada != identificador_vela:
        mensaje_tg = (
            f"🚨 *¡NUEVA SEÑAL SHORT EN BTC/USDT!* 🚨\n\n"
            f"📊 *Score de Confluencia:* {score_short} / {threshold}\n"
            f"💵 *Precio Entrada:* ${precio_actual:,.2f}\n"
            f"🛑 *Stop Loss (1.5%):* ${sl_precio:,.2f}\n"
            f"🎯 *Take Profit (3.0%):* ${tp_precio:,.2f}\n"
            f"⏳ *Temporalidad:* 4h"
        )
        exito = enviar_alerta_telegram(telegram_token, chat_id, mensaje_tg)
        if exito:
            st.success("¡Alerta enviada con éxito a tu Telegram!")
            st.session_state.ultima_alerta_enviada = identificador_vela
else:
    st.success(f"⏳ ESTADO: WAIT (Esperando confluencia bajista clara. Score actual: {score_short})")

# Desglose técnico
with st.expander("Ver métricas técnicas detalladas"):
    st.write(f"- **EMA 20:** ${ema20:,.2f}")
    st.write(f"- **EMA 50:** ${ema50:,.2f}")
    st.write(f"- **ADX (Fuerza de tendencia):** {adx:.2f}")
    st.write(f"- **-DI / +DI:** {minus_di:.2f} / {plus_di:.2f}")

if st.button("Actualizar Datos de Mercado"):
    st.cache_data.clear()
    st.rerun()
