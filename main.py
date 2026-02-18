import json
import websocket
import time
import os
import threading
from collections import deque

# ============================================
# 🔐 API CONFIG (Railway ENV)
# ============================================

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("Missing API_TOKEN or DERIV_APP_ID")

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# ============================================
# ⚙️ SCALPER SETTINGS (Optimized for R_10 & R_25)
# ============================================

SYMBOLS = ["R_10", "R_25"]

STAKE = 10
DURATION = 5
DURATION_UNIT = "t"
CURRENCY = "USD"

# Smaller natural movement detection
MIN_MOVE = {
    "R_10": 0.3,
    "R_25": 0.6,
}

PULLBACK_CONFIRM = {
    "R_10": 0.5,
    "R_25": 0.8,
}

COOLDOWN_SECONDS = 6  # prevents spam trades
LOOKBACK = 25  # fast scalping window

# ============================================
# 📊 DATA STORAGE
# ============================================

price_history = {s: deque(maxlen=200) for s in SYMBOLS}
last_trade_time = {s: 0 for s in SYMBOLS}

# ============================================
# 📈 MICRO TREND DETECTION (Scalping Logic)
# ============================================

def detect_trade(symbol):
    prices = price_history[symbol]

    if len(prices) < LOOKBACK:
        return None

    recent = list(prices)[-LOOKBACK:]

    high = max(recent)
    low = min(recent)
    current = recent[-1]

    move = abs(recent[-1] - recent[-2])

    if move < MIN_MOVE[symbol]:
        return None  # ignore noise only

    # BUY pullback inside micro uptrend
    if current <= low + PULLBACK_CONFIRM[symbol]:
        return "CALL"

    # SELL pullback inside micro downtrend
    if current >= high - PULLBACK_CONFIRM[symbol]:
        return "PUT"

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
    print(f"✅ {symbol} TRADE → {contract_type}")

# ============================================
# 📡 ON MESSAGE
# ============================================

def on_message(ws, message):
    data = json.loads(message)

    if "tick" not in data:
        return

    symbol = data["tick"]["symbol"]
    price = float(data["tick"]["quote"])

    price_history[symbol].append(price)

    now = time.time()

    if now - last_trade_time[symbol] < COOLDOWN_SECONDS:
        return

    signal = detect_trade(symbol)

    if signal:
        print(f"🎯 Entry detected on {symbol}")
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
    print("⚠️ Connection closed — reconnecting...")
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