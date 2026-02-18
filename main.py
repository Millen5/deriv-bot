import json
import websocket
import time
import os
import threading
from collections import deque

# ============================================================
# 🔐 API (Railway Environment Variables)
# ============================================================

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("Missing API_TOKEN or DERIV_APP_ID")

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# ============================================================
# ⚙️ BOT SETTINGS
# ============================================================

SYMBOLS = ["R_75", "R_25"]

STAKE = 10
DURATION = 5
DURATION_UNIT = "t"
CURRENCY = "USD"

# Different sensitivity per market
SPIKE_THRESHOLD_R75 = 12
SPIKE_THRESHOLD_R25 = 6

CONFIRMATION_MOVE = 2
COOLDOWN_SECONDS = 10

ZONE_LOOKBACK = 40  # candles to detect zones

# ============================================================
# 📊 DATA STORAGE
# ============================================================

price_history = {s: deque(maxlen=ZONE_LOOKBACK) for s in SYMBOLS}
last_price = {}
cooldown = {s: False for s in SYMBOLS}

# ============================================================
# 📉 SUPPORT / RESISTANCE DETECTION
# ============================================================

def detect_zones(symbol):
    prices = list(price_history[symbol])

    if len(prices) < 20:
        return None, None

    resistance = max(prices)
    support = min(prices)

    return support, resistance

# ============================================================
# 📈 SPIKE DETECTION WITH ZONE FILTER
# ============================================================

def detect_spike(symbol, price, ws):

    if symbol not in last_price:
        last_price[symbol] = price
        return

    diff = price - last_price[symbol]
    abs_diff = abs(diff)

    # Select threshold per symbol
    if symbol == "R_75":
        spike_threshold = SPIKE_THRESHOLD_R75
    elif symbol == "R_25":
        spike_threshold = SPIKE_THRESHOLD_R25
    else:
        spike_threshold = 12

    support, resistance = detect_zones(symbol)

    if support is None:
        return

    # --------------------------------------------------------
    # SELL only at RESISTANCE
    # --------------------------------------------------------
    if price >= resistance and abs_diff >= spike_threshold and not cooldown[symbol]:

        print(f"🔴 SELL @ Resistance {symbol}")

        confirm_move(symbol, price, ws, "PUT")

    # --------------------------------------------------------
    # BUY only at SUPPORT
    # --------------------------------------------------------
    elif price <= support and abs_diff >= spike_threshold and not cooldown[symbol]:

        print(f"🟢 BUY @ Support {symbol}")

        confirm_move(symbol, price, ws, "CALL")

    last_price[symbol] = price

# ============================================================
# ✅ CONFIRMATION FILTER (ANTI-FAKE SPIKE)
# ============================================================

def confirm_move(symbol, entry_price, ws, contract_type):

    def wait_confirmation():
        time.sleep(1.2)

        current_price = last_price.get(symbol)

        if not current_price:
            return

        move = abs(current_price - entry_price)

        if move >= CONFIRMATION_MOVE:
            send_trade(ws, symbol, contract_type)
            cooldown[symbol] = True

            threading.Thread(target=reset_cooldown, args=(symbol,)).start()
        else:
            print("❌ Fake spike avoided")

    threading.Thread(target=wait_confirmation).start()

# ============================================================
# ⏱️ COOLDOWN
# ============================================================

def reset_cooldown(symbol):
    time.sleep(COOLDOWN_SECONDS)
    cooldown[symbol] = False

# ============================================================
# 💰 SEND TRADE
# ============================================================

def send_trade(ws, symbol, contract_type):

    proposal = {
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

    ws.send(json.dumps(proposal))

    print(f"✅ Trade sent for {symbol} | {contract_type} | Stake {STAKE}")

# ============================================================
# 🔌 WEBSOCKET EVENTS
# ============================================================

def on_open(ws):
    print("🔗 Connected to Deriv")

    auth = {"authorize": API_TOKEN}
    ws.send(json.dumps(auth))

    for symbol in SYMBOLS:
        ws.send(json.dumps({
            "ticks": symbol,
            "subscribe": 1
        }))

def on_message(ws, message):

    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        price = float(data["tick"]["quote"])

        price_history[symbol].append(price)

        detect_spike(symbol, price, ws)

def on_error(ws, error):
    print("❌ Error:", error)

def on_close(ws, a, b):
    print("🔌 Connection Closed")

# ============================================================
# 🚀 START BOT
# ============================================================

def start():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

start()