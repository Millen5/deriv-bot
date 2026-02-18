import json
import websocket
import time
import os
import threading

# 🔐 Tunachukua Token + App ID kutoka Railway Variables
API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

# Hakikisha zipo
if not API_TOKEN or not DERIV_APP_ID:
    raise Exception("API_TOKEN au DERIV_APP_ID haijawekwa kwenye Environment Variables")

# ⚙️ Settings za Bot
SYMBOLS = ["R_75"]        # unaweza kuongeza R_100, R_50 baadae
STAKE = 0.005             # lot size yako
SPIKE_THRESHOLD = 12      # spike strength (unaweza badilisha)

# Storage
last_prices = {s: None for s in SYMBOLS}
cooldown = {s: False for s in SYMBOLS}


def authorize(ws):
    auth_data = {
        "authorize": API_TOKEN
    }
    ws.send(json.dumps(auth_data))


def send_trade(ws, symbol, contract_type):
    trade = {
        "buy": 1,
        "price": STAKE,
        "parameters": {
            "amount": STAKE,
            "basis": "stake",
            "contract_type": contract_type,  # CALL au PUT
            "currency": "USD",
            "duration": 2,
            "duration_unit": "t",
            "symbol": symbol
        }
    }

    ws.send(json.dumps(trade))
    print(f"✅ Trade sent for {symbol} | Direction: {contract_type} | Stake: {STAKE}")


def reset(symbol):
    time.sleep(5)  # cooldown sekunde 5
    cooldown[symbol] = False


def detect_spike(symbol, price, ws):
    if last_prices[symbol] is None:
        last_prices[symbol] = price
        return

    price_change = price - last_prices[symbol]
    diff = abs(price_change)

    if diff >= SPIKE_THRESHOLD and not cooldown[symbol]:

        # Spike UP → SELL (Fall)
        if price_change > 0:
            contract_type = "PUT"

        # Spike DOWN → BUY (Rise)
        else:
            contract_type = "CALL"

        print(f"🔥 Spike detected on {symbol}: {diff} | Direction: {contract_type}")

        send_trade(ws, symbol, contract_type)

        cooldown[symbol] = True
        threading.Thread(target=reset, args=(symbol,)).start()

    last_prices[symbol] = price


def on_message(ws, message):
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        price = float(data["tick"]["quote"])
        detect_spike(symbol, price, ws)


def on_open(ws):
    print("🔗 Connected to Deriv")

    authorize(ws)

    for symbol in SYMBOLS:
        sub = {
            "ticks": symbol,
            "subscribe": 1
        }
        ws.send(json.dumps(sub))


def on_error(ws, error):
    print("❌ Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed. Reconnecting...")
    time.sleep(3)
    start()


def start():
    url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever()


start()