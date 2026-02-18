import json
import websocket
import time
import os
import threading
from statistics import mean

# ============================================
# 🔐 API CONFIG (Railway Variables)
# ============================================

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("Missing API_TOKEN or DERIV_APP_ID")

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# ============================================
# ⚙️ BOT SETTINGS (STABLE MODE)
# ============================================

SYMBOLS = ["R_25", "R_10"]  # ✅ Stable indices

STAKE = 3                   # lower risk (important!)
DURATION = 6                # slightly longer = safer
DURATION_UNIT = "t"
CURRENCY = "USD"

ZONE_LOOKBACK = 50          # candles to detect zones
CONFIRMATION_RANGE = 2.5    # how close to zone before entry
COOLDOWN_SECONDS = 15       # avoid overtrading

MIN_VOLATILITY = 0.8        # avoid dead market
TREND_PERIOD = 20           # trend detection

# ============================================
# 📊 STORAGE
# ============================================

price_history = {s: [] for s in SYMBOLS}
last_trade_time = {s: 0 for s in SYMBOLS}

# ============================================
# 📈 SUPPORT / RESISTANCE DETECTION
# ============================================

def detect_zones(symbol):
    prices = price_history[symbol]

    if len(prices) < ZONE_LOOKBACK:
        return None, None

    recent = prices[-ZONE_LOOKBACK:]

    support = min(recent)
    resistance = max(recent)

    return support, resistance

# ============================================
# 📊 VOLATILITY FILTER
# ============================================

def market_is_active(symbol):
    prices = price_history[symbol]

    if len(prices) < 10:
        return False

    moves = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
    avg_move = mean(moves[-10:])

    return avg_move >= MIN_VOLATILITY

# ============================================
# 📉 TREND FILTER (VERY IMPORTANT)
# ============================================

def detect_trend(symbol):
    prices = price_history[symbol]

    if len(prices) < TREND_PERIOD:
        return None

    recent = prices[-TREND_PERIOD:]
    avg_price = mean(recent)

    if prices[-1] > avg_price:
        return "UP"
    elif prices[-1] < avg_price:
        return "DOWN"
    else:
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
    print(f"✅ Trade sent: {symbol} | {contract_type}")

# ============================================
# 📡 ON TICK MESSAGE
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

    support, resistance = detect_zones(symbol)

    if support is None:
        return

    now = time.time()

    # Cooldown protection
    if now - last_trade_time[symbol] < COOLDOWN_SECONDS:
        return

    # Skip if market dead
    if not market_is_active(symbol):
        print(f"⏸ Market slow — skipping {symbol}")
        return

    trend = detect_trend(symbol)

    # ============================================
    # 🟢 BUY ONLY IF TREND IS UP + AT SUPPORT
    # ============================================

    if trend == "UP" and abs(price - support) <= CONFIRMATION_RANGE:
        print(f"🟢 BUY @{symbol} Support | Trend UP")
        send_trade(ws, symbol, "CALL")
        last_trade_time[symbol] = now
        return

    # ============================================
    # 🔴 SELL ONLY IF TREND IS DOWN + AT RESISTANCE
    # ============================================

    if trend == "DOWN" and abs(price - resistance) <= CONFIRMATION_RANGE:
        print(f"🔴 SELL @{symbol} Resistance | Trend DOWN")
        send_trade(ws, symbol, "PUT")
        last_trade_time[symbol] = now
        return

# ============================================
# 🔐 CONNECT EVENTS
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
# ▶️ START BOT
# ============================================

threading.Thread(target=connect).start()

# Keep Railway alive
while True:
    time.sleep(1)