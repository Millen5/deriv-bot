import json
import websocket
import time
import os
import threading

# ============================================
# 🔐 API CONFIG (From Railway Variables)
# ============================================

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("Missing API_TOKEN or DERIV_APP_ID")

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# ============================================
# ⚙️ BOT SETTINGS
# ============================================

SYMBOLS = ["R_75", "R_25"]

STAKE = 10
DURATION = 5
DURATION_UNIT = "t"
CURRENCY = "USD"

# Different sensitivity for each index
SPIKE_THRESHOLD = {
    "R_75": 14,
    "R_25": 7,
}

CONFIRMATION_MOVE = 5
COOLDOWN_SECONDS = 10

ZONE_LOOKBACK = 35  # number of ticks to detect zones

# ============================================
# 📊 DATA STORAGE
# ============================================

price_history = {s: [] for s in SYMBOLS}
last_trade_time = {s: 0 for s in SYMBOLS}

# ============================================
# 📈 ZONE DETECTION
# ============================================

def detect_support_resistance(symbol):
    prices = price_history[symbol]

    if len(prices) < ZONE_LOOKBACK:
        return None, None

    recent = prices[-ZONE_LOOKBACK:]

    support = min(recent)
    resistance = max(recent)

    return support, resistance

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
    print(f"✅ Trade sent for {symbol} | {contract_type}")

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

    if len(price_history[symbol]) > 200:
        price_history[symbol].pop(0)

    support, resistance = detect_support_resistance(symbol)

    if support is None:
        return

    now = time.time()

    if now - last_trade_time[symbol] < COOLDOWN_SECONDS:
        return

    threshold = SPIKE_THRESHOLD[symbol]

    if len(price_history[symbol]) < 2:
        return

    move = abs(price_history[symbol][-1] - price_history[symbol][-2])

    if move < threshold:
        return

    # ============================================
    # 🟢 BUY at SUPPORT
    # ============================================

    if abs(price - support) <= CONFIRMATION_MOVE:
        print(f"🟢 BUY @ Support {symbol}")
        send_trade(ws, symbol, "CALL")
        last_trade_time[symbol] = now
        return

    # ============================================
    # 🔴 SELL at RESISTANCE
    # ============================================

    if abs(price - resistance) <= CONFIRMATION_MOVE:
        print(f"🔴 SELL @ Resistance {symbol}")
        send_trade(ws, symbol, "PUT")
        last_trade_time[symbol] = now
        return

# ============================================
# 🔐 AUTHORIZE
# ============================================

def on_open(ws):
    print("🔗 Connected to Deriv")

    auth = {"authorize": API_TOKEN}
    ws.send(json.dumps(auth))

    for symbol in SYMBOLS:
        sub = {"ticks": symbol, "subscribe": 1}
        ws.send(json.dumps(sub))
        print(f"📡 Subscribed to {symbol}")

def on_error(ws, error):
    print("❌ Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("⚠️ Connection closed — reconnecting in 5s...")
    time.sleep(5)
    connect()

# ============================================
# 🔁 CONNECT FUNCTION
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
# ▶️ START BOT THREAD
# ============================================

threading.Thread(target=connect).start()

# ============================================
# 🛑 KEEP ALIVE (IMPORTANT FOR RAILWAY)
# ============================================

while True:
    time.sleep(1)