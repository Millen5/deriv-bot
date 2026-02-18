import json
import websocket
import time
import os
import threading
from collections import deque

# ============================================
# 🔐 LOAD ENV VARIABLES (Railway Variables)
# ============================================

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("Missing API_TOKEN or DERIV_APP_ID in environment variables.")

# ============================================
# ⚙️ BOT SETTINGS
# ============================================

SYMBOLS = ["R_75", "R_25"]

STAKE = 10                # Amount per trade
DURATION = 5              # Contract duration
DURATION_UNIT = "t"       # ticks
CURRENCY = "USD"

SPIKE_THRESHOLD = 18      # Minimum spike size to analyze
CONFIRMATION_MOVE = 5     # Wait before entering trade
COOLDOWN_SECONDS = 10      # Wait after trade before next

ZONE_LOOKBACK = 60        # Candles to detect zones

# ============================================
# 📊 DATA STORAGE
# ============================================

price_history = {s: deque(maxlen=ZONE_LOOKBACK) for s in SYMBOLS}
cooldown = {s: False for s in SYMBOLS}
last_touch_buy = {s: None for s in SYMBOLS}
last_touch_sell = {s: None for s in SYMBOLS}

# ============================================
# 🔌 CONNECT TO DERIV
# ============================================

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"


def on_open(ws):
    print("✅ Connected to Deriv")

    authorize = {
        "authorize": API_TOKEN
    }
    ws.send(json.dumps(authorize))

    for symbol in SYMBOLS:
        subscribe_ticks(ws, symbol)


def subscribe_ticks(ws, symbol):
    msg = {
        "ticks": symbol,
        "subscribe": 1
    }
    ws.send(json.dumps(msg))
    print(f"📡 Subscribed to {symbol}")


# ============================================
# 📥 RECEIVE MARKET DATA
# ============================================

def on_message(ws, message):
    data = json.loads(message)

    if "tick" not in data:
        return

    symbol = data["tick"]["symbol"]
    price = data["tick"]["quote"]

    process_price(ws, symbol, price)


# ============================================
# 🧠 CORE LOGIC
# ============================================

def process_price(ws, symbol, price):
    price_history[symbol].append(price)

    if len(price_history[symbol]) < ZONE_LOOKBACK:
        return

    if cooldown[symbol]:
        return

    detect_zones_and_trade(ws, symbol, price)


# ============================================
# 📐 SUPPORT / RESISTANCE DETECTION
# ============================================

def detect_zones_and_trade(ws, symbol, price):
    history = list(price_history[symbol])

    support = min(history)
    resistance = max(history)

    zone_size = resistance - support

    if zone_size < SPIKE_THRESHOLD:
        return

    # ========================================
    # BUY LOGIC (Support Rejection)
    # ========================================

    if price <= support:
        last_touch_buy[symbol] = price
        print(f"🔎 {symbol} touched SUPPORT")

    if last_touch_buy[symbol] is not None:
        if price >= last_touch_buy[symbol] + CONFIRMATION_MOVE:
            print(f"✅ BUY confirmed on {symbol}")
            place_trade(ws, symbol, "CALL")
            last_touch_buy[symbol] = None
            start_cooldown(symbol)

    # ========================================
    # SELL LOGIC (Resistance Rejection)
    # ========================================

    if price >= resistance:
        last_touch_sell[symbol] = price
        print(f"🔎 {symbol} touched RESISTANCE")

    if last_touch_sell[symbol] is not None:
        if price <= last_touch_sell[symbol] - CONFIRMATION_MOVE:
            print(f"✅ SELL confirmed on {symbol}")
            place_trade(ws, symbol, "PUT")
            last_touch_sell[symbol] = None
            start_cooldown(symbol)


# ============================================
# 💰 EXECUTE TRADE
# ============================================

def place_trade(ws, symbol, contract_type):
    trade = {
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

    ws.send(json.dumps(trade))

    print(f"🚀 Trade Sent | {symbol} | {contract_type} | Stake {STAKE}")


# ============================================
# ⏳ COOLDOWN SYSTEM
# ============================================

def start_cooldown(symbol):
    cooldown[symbol] = True

    def reset():
        time.sleep(COOLDOWN_SECONDS)
        cooldown[symbol] = False

    threading.Thread(target=reset).start()


# ============================================
# ❌ ERROR HANDLING
# ============================================

def on_error(ws, error):
    print("❌ Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection Closed. Reconnecting...")
    time.sleep(5)
    start()


# ============================================
# ▶️ START BOT
# ============================================

def start():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever()


if __name__ == "__main__":
    start()