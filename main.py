import json
import websocket
import time
import os
import threading
from collections import deque
import statistics

# ============================================
# 🔐 API CONFIG
# ============================================

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("Missing API_TOKEN or DERIV_APP_ID")

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# ============================================
# ⚙️ SNIPER SETTINGS (Mean Reversion)
# ============================================

SYMBOLS = ["R_10", "R_25"]

STAKE = 20
DURATION = 5
DURATION_UNIT = "t"
CURRENCY = "USD"

LOOKBACK = 40          # history used to calculate mean
DEVIATION_FACTOR = 2.2 # how far price must stretch
COOLDOWN = 12          # wait between trades

# ============================================
# 📊 DATA STORAGE
# ============================================

price_history = {s: deque(maxlen=200) for s in SYMBOLS}
last_trade_time = {s: 0 for s in SYMBOLS}

# ============================================
# 📈 MEAN REVERSION LOGIC
# ============================================

def detect_sniper_entry(symbol):
    prices = price_history[symbol]

    if len(prices) < LOOKBACK:
        return None

    data = list(prices)[-LOOKBACK:]

    mean_price = statistics.mean(data)
    std_dev = statistics.stdev(data)

    current_price = data[-1]

    upper_band = mean_price + (std_dev * DEVIATION_FACTOR)
    lower_band = mean_price - (std_dev * DEVIATION_FACTOR)

    # 🔴 Overbought → Expect drop
    if current_price > upper_band:
        print(f"📉 {symbol} EXTREME HIGH → SELL")
        return "PUT"

    # 🟢 Oversold → Expect bounce
    if current_price < lower_band:
        print(f"📈 {symbol} EXTREME LOW → BUY")
        return "CALL"

    return None

# ============================================
# 🚀 SEND TRADE
# ============================================

def send_trade(ws, symbol, contract_type):
    order = {
        "buy": 1,
        "price": STAKE,
        "parameters": {
            "amount": STAKE,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": CURRENCY,
            "duration": DURATION,
            "duration_unit": DURATION_UNIT,
            "symbol": symbol
        }
    }

    ws.send(json.dumps(order))
    print(f"✅ TRADE EXECUTED | {symbol} | {contract_type}")

# ============================================
# 📡 STREAM HANDLER
# ============================================

def on_message(ws, message):
    data = json.loads(message)

    if "tick" not in data:
        return

    symbol = data["tick"]["symbol"]
    price = float(data["tick"]["quote"])

    price_history[symbol].append(price)

    now = time.time()

    if now - last_trade_time[symbol] < COOLDOWN:
        return

    signal = detect_sniper_entry(symbol)

    if signal:
        send_trade(ws, symbol, signal)
        last_trade_time[symbol] = now

# ============================================
# 🔐 CONNECTION EVENTS
# ============================================

def on_open(ws):
    print("🔗 Connected to Deriv")

    ws.send(json.dumps({"authorize": API_TOKEN}))

    for symbol in SYMBOLS:
        ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
        print(f"📡 Subscribed to {symbol}")

def on_error(ws, error):
    print("❌ Error:", error)

def on_close(ws, code, msg):
    print("⚠️ Reconnecting...")
    time.sleep(3)
    connect()

# ============================================
# 🔁 CONNECT
# ============================================

def connect():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ============================================
# ▶️ START BOT
# ============================================

threading.Thread(target=connect).start()

while True:
    time.sleep(1)