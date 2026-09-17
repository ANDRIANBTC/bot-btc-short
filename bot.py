import os
import time
import ccxt
import pandas as pd
import numpy as np
import requests

# Credenciales desde las variables de entorno del sistema (o Secrets de GitHub)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_alerta_telegram(mensaje):
    """Función para enviar alertas automáticas vía Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram no configuradas.")
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
    except Exception as e:
        print(f"Error al enviar alerta a Telegram: {e}")
        return False

def cargar_y_analizar_datos():
    """Descarga datos de Kraken y calcula indicadores técnicos"""
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

def ejecutar_bot():
    print("🔄 Analizando mercado de BTC/USDT en Kraken...")
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
        minus_di = float(ultima_vela['minus_di'])
        plus_di = float(ultima_vela['plus_di'])

        threshold = 78.0
        sl_pct = 0.015
        tp_pct = 0.030

        score_short = 0.0
        if precio_actual < ema20 and ema20 < ema50: score_short += 25.0
        if ema20 < ema50: score_short += 15.0
        if (rsi > 65) or (35 <= rsi <= 50): score_short += 15.0
        if rsi < rsi_prev: score_short += 10.0
        if adx > 25: score_short += 15.0
        if minus_di > plus_di: score_short += 20.0

        print(f"📊 Precio actual: ${precio_actual:,.2f} | Score Short: {score_short} / {threshold}")

        if score_short >= threshold:
            sl_precio = precio_actual * (1.0 + sl_pct)
            tp_precio = precio_actual * (1.0 - tp_pct)
            
            identificador_vela = str(ultima_vela['timestamp'])
            
            mensaje_tg = (
                f"🚨 *¡NUEVA SEÑAL SHORT EN BTC/USDT!* 🚨\n\n"
                f"📊 *Score de Confluencia:* {score_short} / {threshold}\n"
                f"💵 *Precio Entrada:* ${precio_actual:,.2f}\n"
                f"🛑 *Stop Loss (1.5%):* ${sl_precio:,.2f}\n"
                f"🎯 *Take Profit (3.0%):* ${tp_precio:,.2f}\n"
                f"⏳ *Temporalidad:* 4h"
            )
            
            # Nota: En GitHub Actions puedes guardar un registro temporal o simplemente disparar la alerta
            exito = enviar_alerta_telegram(mensaje_tg)
            if exito:
                print("✅ ¡Alerta enviada con éxito a Telegram!")
        else:
            print("⏳ Estado: WAIT (Sin confluencia bajista suficiente).")

    except Exception as e:
        print(f"⚠️ Error al ejecutar el análisis: {e}")

if __name__ == "__main__":
    ejecutar_bot()
