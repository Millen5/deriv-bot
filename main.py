import json
import websocket
import time
import os

# 🔐 Tunachukua Token + App ID kutoka Railway Variables
API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

# Hakikisha zipo
if not API_TOKEN or not DERIV_APP_ID:
    raise ValueError("API_TOKEN or DERIV_APP_ID missing in environment variables")

# 🌐 WebSocket URL yenye App ID yako
WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# 📊 Markets tutakazotrade
SYMBOLS = ["BOOM500", "BOOM1000", "R_10", "R_25", "R_75"]

# 💰 Lot size kwa kila market (badili hapa ukitaka)
STAKES = {
    "BOOM500": 0.3,
    "BOOM1000": 0.3,
    "R_10": 0.5,
    "R_25": 0.5,
    "R_75": 0.005
}

SPIKE_THRESHOLD = 5
last_prices = {}
cooldown = {}

def send_trade(ws, symbol):
    stake = STAKES[symbol]

    order = {
        "buy": 1,
        "price": stake,
        "parameters": {
            "amount": stake,
            "basis": "stake",
            "contract_type": "CALL",
            "currency": "USD",
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }
    }

    ws.send(json.dumps(order))
    print(f"✅ Trade sent for {symbol} | Stake: {stake}")

def detect_spike(symbol, price, ws):
    if last_prices[symbol] is None:
        last_prices[symbol] = price
        return

    diff = abs(price - last_prices[symbol])

    if diff >= SPIKE_THRESHOLD and not cooldown[symbol]:
        print(f"🔥 Spike detected on {symbol}: {diff}")
        send_trade(ws, symbol)
        cooldown[symbol] = True

        # Reset cooldown baada ya sekunde 5
        def reset():
            time.sleep(5)
            cooldown[symbol] = False

        import threading
        threading.Thread(target=reset).start()

    last_prices[symbol] = price

def on_open(ws):
    print("✅ Connected to Deriv")

    # Authorize
    auth = {"authorize": API_TOKEN}
    ws.send(json.dumps(auth))

    # Subscribe ticks
    for symbol in SYMBOLS:
        tick = {"ticks": symbol, "subscribe": 1}
        ws.send(json.dumps(tick))
        last_prices[symbol] = None
        cooldown[symbol] = False

def on_message(ws, message):
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        price = data["tick"]["quote"]
        detect_spike(symbol, price, ws)

    elif "buy" in data:
        print("📈 CONTRACT OPENED:", data["buy"])

    elif "error" in data:
        print("❌ ERROR:", data["error"])

def on_error(ws, error):
    print("❌ WebSocket Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed")

def start():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    ws.run_forever()

if __name__ == "__main__":
    start()