import json
import websocket
import time
import os

# 🔐 Token inachukuliwa Railway Variables (USIWEKE token hapa)
API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

# Markets tutakazotrade
SYMBOLS = ["BOOM500", "BOOM1000", "R_10", "R_25", "R_75"]

# Lot size kwa kila market (ulivyoomba)
STAKES = {
    "BOOM500": 0.3,
    "BOOM1000": 0.3,
    "R_10": 0.5,
    "R_25": 0.5,
    "R_75": 0.005
}

SPIKE_THRESHOLD = 5  # nguvu ya spike kugundua
last_prices = {}
cooldown = {}

def on_open(ws):
    print("✅ Connected to Deriv")

    # Authorize
    auth = {"authorize": API_TOKEN}
    ws.send(json.dumps(auth))

    # Subscribe ticks for all symbols
    for symbol in SYMBOLS:
        tick = {"ticks": symbol, "subscribe": 1}
        ws.send(json.dumps(tick))
        last_prices[symbol] = None
        cooldown[symbol] = False


def detect_spike(symbol, price, ws):
    global last_prices, cooldown

    if last_prices[symbol] is None:
        last_prices[symbol] = price
        return

    movement = abs(price - last_prices[symbol])

    if movement >= SPIKE_THRESHOLD and not cooldown[symbol]:
        print(f"🔥 Spike detected on {symbol}: {movement}")
        place_trade(ws, symbol)
        cooldown[symbol] = True
        time.sleep(2)
        cooldown[symbol] = False

    last_prices[symbol] = price


def place_trade(ws, symbol):
    stake = STAKES[symbol]

    order = {
        "buy": 1,
        "price": stake,
        "parameters": {
            "amount": stake,
            "basis": "stake",
            "contract_type": "CALL",
            "currency": "USD",
            "duration": 5,
            "duration_unit": "t",
            "symbol": symbol
        }
    }

    ws.send(json.dumps(order))
    print(f"✅ Trade sent for {symbol} | Stake: {stake}")


def on_message(ws, message):
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        price = data["tick"]["quote"]
        detect_spike(symbol, price, ws)


def on_error(ws, error):
    print("❌ Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed")


def start():
    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever()


if __name__ == "__main__":
    start()
