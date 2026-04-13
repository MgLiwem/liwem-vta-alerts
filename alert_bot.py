#!/usr/bin/env python3
import os, requests, json, time
from datetime import datetime
from groq import Groq
import yfinance as yf
import ccxt

# ===== CONFIG (Loaded securely from GitHub Secrets later) =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ===== YOUR WATCHLIST =====
MARKETS = [
    {"symbol": "EURUSD=X", "name": "EUR/USD", "type": "forex"},
    {"symbol": "GBPUSD=X", "name": "GBP/USD", "type": "forex"},
    {"symbol": "XAUUSD=X", "name": "Gold", "type": "forex"},
    {"symbol": "BTC-USD", "name": "Bitcoin", "type": "crypto"},
    {"symbol": "ETH-USD", "name": "Ethereum", "type": "crypto"},
    {"symbol": "PEPE-USD", "name": "Pepe", "type": "crypto"},
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })

def get_price_data(symbol, mtype):
    try:
        if mtype == "crypto":
            exchange = ccxt.binance()
            ticker = exchange.fetch_ticker(symbol.replace("-USD", "/USDT"))
            return {
                "price": ticker["last"],
                "change_24h": ticker["percentage"],
                "volume": ticker["quoteVolume"]
            }
        else:
            data = yf.Ticker(symbol).history(period="5d")
            current = data["Close"].iloc[-1]
            prev = data["Close"].iloc[-2]
            return {
                "price": current,
                "change_24h": ((current - prev) / prev) * 100,
                "volume": data["Volume"].iloc[-1]
            }
    except:
        return {"price": 0, "change_24h": 0, "volume": 0}

def analyze_with_ai(name, mtype, data):
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""You are a professional trading analyst. Analyze {name} ({mtype}):
Current Data:
- Price: {data['price']:.4f if isinstance(data['price'], float) else data['price']}
- 24h Change: {data['change_24h']:.2f}%
- Volume: {data['volume']:,.0f}

Give a clear trading signal with:
1. Signal: BUY, SELL, or WAIT
2. Entry price (approximate)
3. Stop Loss (SL)
4. Take Profit (TP)
5. Confidence level (0-100%)
6. One short reason why

Return ONLY this JSON format (no extra text):
{{
  "signal": "BUY",
  "entry": 1.0850,
  "sl": 1.0800,
  "tp": 1.0950,
  "confidence": 75,
  "reason": "Brief explanation"
}}"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400
        )
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"AI error: {e}")
        return None

def format_alert(name, data, analysis):
    emoji = "🟢" if analysis["signal"]=="BUY" else "🔴" if analysis["signal"]=="SELL" else "⚪"
    return f"""
{emoji} *{name}* {analysis["signal"]}
💰 Entry: `{analysis["entry"]}`
🛑 SL: `{analysis["sl"]}`
🎯 TP: `{analysis["tp"]}`
📊 Confidence: {analysis["confidence"]}%
📝 {analysis["reason"]}
📈 24h: {data["change_24h"]:+.2f}%
⏰ {datetime.now().strftime('%H:%M UTC, %Y-%m-%d')}
    """.strip()

def main():
    alerts_sent = 0
    for m in MARKETS:
        print(f"Analyzing {m['name']}...")
        data = get_price_data(m["symbol"], m["type"])
        if data["price"] == 0:
            continue
        analysis = analyze_with_ai(m["name"], m["type"], data)
        if not analysis or analysis.get("signal") == "WAIT":
            continue
        message = format_alert(m["name"], data, analysis)
        send_telegram(message)
        alerts_sent += 1
        time.sleep(3)
    if alerts_sent == 0:
        send_telegram("🔍 Scan complete. No high-conviction signals found.")
    else:
        send_telegram(f"✅ Sent {alerts_sent} signal(s).")

if __name__ == "__main__":
    main()
