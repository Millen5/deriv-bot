import json
import websocket
import time
import os
import threading
from collections import deque

API_TOKEN = os.getenv("API_TOKEN")
DERIV_APP_ID = os.getenv("DERIV_APP_ID")

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

SYMBOLS = ["R_10", "R_25"]

STAKE = 20
DURATION = 5
DURATION_UNIT = "t"
CURRENCY = "USD"

LOOKBACK = 60           # history ya kutengeneza range
BREAK_BUFFER = 1.2      # lazima ivunje level kidogo
REJECTION_BUFFER = 0.6  # lazima irudi ndani
COOLDOWN = 25           # hakuna trade nyingine haraka

price_history = {s: deque(maxlen=300) for s in SYMBOLS}
last_trade_time = {s: 0 for s in SYMBOLS}


def detect_rejection(symbol):
    prices = list(price_history[symbol])
    if len(prices) < LOOKBACK:
        return None

    recent = prices[-LOOKBACK:]

    high = max(recent)
    low = min(recent)
    current = recent[-1]
    prev = recent[-2]

    # 🔴 Fake breakout above resistance → SELL
    if prev > high - BREAK_BUFFER and current < high - REJECTION_BUFFER:
        print(f"{symbol} rejection from HIGH → SELL")
        return "PUT"

    # 🟢 Fake breakout below support → BUY
    if prev < low + BREAK_BUFFER and current > low + REJECTION_BUFFER:
        print(f"{symbol} rejection from LOW → BUY")
        return "CALL"

    return None


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
    print(f"TRADE → {symbol} {contract_type}")


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

    signal = detect_rejection(symbol)

    if signal:
        send_trade(ws, symbol, signal)
        last_trade_time[symbol] = now


def on_open(ws):
    print("Connected to Deriv")

    ws.send(json.dumps({"authorize": API_TOKEN}))

    for symbol in SYMBOLS:
        ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
        print(f"Subscribed to {symbol}")


def connect():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message
    )
    ws.run_forever()


threading.Thread(target=connect).start()

while True:
    time.sleep(1)