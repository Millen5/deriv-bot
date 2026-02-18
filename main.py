import json
import websocket
import time
import os
import threading

# ==============================
# 🔐 API kutoka Railway Variables
# ==============================
API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("API_TOKEN au DERIV_APP_ID haipo kwenye Environment Variables")

# ==============================
# ⚙️ SETTINGS
# ==============================
SYMBOLS = ["R_75", "R_25"]   # Multi-symbol trading
SPIKE_THRESHOLD = 12         # nguvu ya move lazima iwe kubwa
STAKE = 10                   # stake ya trade
DURATION = 3                 # ticks (scalp nzuri kwa synthetics)

# ==============================
# 🧠 STORAGE (kila symbol ina data yake)
# ==============================
last_prices = {}
price_history = {}
cooldown = {}

# ==============================
# 🔌 CONNECT
# ==============================
def on_open(ws):
    print("✅ Connected to Deriv")

    auth = {"authorize": API_TOKEN}
    ws.send(json.dumps(auth))

def subscribe_ticks(ws):
    for symbol in SYMBOLS:
        sub = {
            "ticks": symbol,
            "subscribe": 1
        }
        ws.send(json.dumps(sub))

# ==============================
# 📊 DETECT MICRO STRUCTURE
# ==============================
def detect_structure_zone(symbol):
    if symbol not in price_history or len(price_history[symbol]) < 5:
        return None, None

    prices = price_history[symbol]
    p1, p2, p3, p4, p5 = prices[-5:]

    support = None
    resistance = None

    # Swing Low → Support
    if p3 < p2 and p3 < p4:
        support = p3

    # Swing High → Resistance
    if p3 > p2 and p3 > p4:
        resistance = p3

    return support, resistance

# ==============================
# 🚀 SEND TRADE
# ==============================
def send_trade(ws, symbol, contract_type):

    trade = {
        "buy": 1,
        "price": STAKE,
        "parameters": {
            "amount": STAKE,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": DURATION,
            "duration_unit": "t",
            "symbol": symbol
        }
    }

    ws.send(json.dumps(trade))
    print(f"📈 Trade sent | {symbol} | {contract_type} | Stake {STAKE}")

# ==============================
# ⏱ COOLDOWN RESET
# ==============================
def reset_cooldown(symbol):
    time.sleep(5)
    cooldown[symbol] = False

# ==============================
# 🔍 MAIN LOGIC
# ==============================
def detect_spike(ws, symbol, price):

    if symbol not in last_prices:
        last_prices[symbol] = price
        cooldown[symbol] = False
        price_history[symbol] = []
        return

    # store history
    price_history[symbol].append(price)
    if len(price_history[symbol]) > 100:
        price_history[symbol].pop(0)

    # calculate movement
    price_change = price - last_prices[symbol]
    diff = abs(price_change)

    # lazima iwe spike
    if diff < SPIKE_THRESHOLD or cooldown[symbol]:
        last_prices[symbol] = price
        return

    support, resistance = detect_structure_zone(symbol)

    if support:
        print(f"🟢 SUPPORT detected {symbol} @ {support}")
        contract_type = "CALL"

    elif resistance:
        print(f"🔴 RESISTANCE detected {symbol} @ {resistance}")
        contract_type = "PUT"

    else:
        last_prices[symbol] = price
        return

    print(f"🔥 Spike confirmed {symbol} move {diff}")

    send_trade(ws, symbol, contract_type)

    cooldown[symbol] = True
    threading.Thread(target=reset_cooldown, args=(symbol,)).start()

    last_prices[symbol] = price

# ==============================
# 📩 RECEIVE DATA
# ==============================
def on_message(ws, message):
    data = json.loads(message)

    if "authorize" in data:
        subscribe_ticks(ws)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        price = float(data["tick"]["quote"])
        detect_spike(ws, symbol, price)

def on_error(ws, error):
    print("❌ Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed")

# ==============================
# ▶️ START
# ==============================
socket = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

ws = websocket.WebSocketApp(
    socket,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()