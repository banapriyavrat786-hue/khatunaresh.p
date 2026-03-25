import time, os, pandas as pd
from api_helper import ShoonyaApiPy

# ========= CONFIG =========
USER, PWD, VC, KEY = "YOUR_ID", "YOUR_PASS", "YOUR_VC", "YOUR_KEY"
MAX_TRADES = 5
COOLDOWN = 60
# Note: Adjust MAX_DAILY_LOSS to points * lot size (e.g., -1000 for 20 pts Nifty)
MAX_DAILY_LOSS = -2000 

api = ShoonyaApiPy()

# ========= GLOBAL STATS =========
trade_count = 0
daily_pnl = 0
last_trade_time = 0
locked_entry = 0
trade_type = None
trail_sl = 0
prev_oi = 0
prev_price = 0

# ========= TECHNICALS =========
def rsi_calc(series, period=14):
    """Standard RSI with Wilder's Smoothing (EWM)"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def fetch_data(token):
    try:
        # 1. Get Live Quote
        q = api.get_quotes(exchange="NSE", token=token)
        if not q or 'lp' not in q: return None
        
        lp = float(q['lp'])
        toi = int(q.get('toi', 0))
        vol = int(q.get('v', 0))

        # 2. Get Historical for Indicators (5-min candles)
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if not hist or len(hist) < 30: return None

        df = pd.DataFrame(hist)
        df['intc'] = df['intc'].astype(float)
        df['v'] = df['v'].astype(float)

        # Indicators
        sma = df['intc'].rolling(20).mean().iloc[-1]
        rsi = rsi_calc(df['intc']).iloc[-1]
        
        # VWAP Calculation
        df['vwap'] = (df['intc'] * df['v']).cumsum() / df['v'].cumsum()
        vwap = df['vwap'].iloc[-1]

        avg_vol = df['v'].tail(10).mean()
        prev_high = df['intc'].tail(5).max()
        prev_low = df['intc'].tail(5).min()

        return lp, sma, rsi, vwap, vol, toi, avg_vol, prev_high, prev_low
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

# ========= EXECUTION =========
def place_market_order(buy_sell, symbol, qty):
    """Safety wrapper for API orders"""
    try:
        res = api.place_order(buy_or_sell=buy_sell, product_type='I',
                             exchange='NFO', tradingsymbol=symbol,
                             quantity=qty, discloseqty=0, price_type='MKT',
                             remarks='UltraBot_Trade')
        return res
    except Exception as e:
        print(f"Order Failed: {e}")
        return None

# ========= MAIN LOOP =========
def main():
    global locked_entry, trade_type, trade_count, daily_pnl
    global last_trade_time, prev_oi, prev_price, trail_sl

    # Setup
    idx = input("1. NIFTY (26000) | 2. BANKNIFTY (26009): ")
    token = "26000" if idx == "1" else "26009"
    qty = 50 if idx == "1" else 15 # Standard Lot Sizes
    
    totp = input("Enter TOTP: ").strip()
    login = api.login(userid=USER, password=PWD, twoFA=totp,
                      vendor_code=VC, api_secret=KEY, imei="abc123")

    if not login or login.get('stat') != 'Ok':
        print("❌ Login Failed!")
        return

    print("✅ BOT LIVE - SCANNING FOR SNIPER ENTRIES...")

    while True:
        now = time.time()
        
        # Risk Check
        if trade_count >= MAX_TRADES or daily_pnl <= MAX_DAILY_LOSS:
            print("🛑 Trading Stopped: Limits Reached.")
            break

        data = fetch_data(token)
        if data:
            lp, sma, rsi, vwap, vol, toi, avg_vol, prev_high, prev_low = data
            
            # Logic Helpers
            oi_change = toi - prev_oi if prev_oi else 0
            vol_spike = vol > (avg_vol * 1.5)
            
            # SIGNAL LOGIC
            signal = "WAIT"
            if lp > sma and lp > vwap and rsi > 55 and vol_spike and lp > prev_high:
                signal = "STRONG CALL 🟢"
            elif lp < sma and lp < vwap and rsi < 45 and vol_spike and lp < prev_low:
                signal = "STRONG PUT 🔴"

            # Console Refresh
            os.system("cls" if os.name == "nt" else "clear")
            print(f"--- SNIPER | {time.strftime('%H:%M:%S')} ---")
            print(f"LTP: {lp} | RSI: {round(rsi,1)} | VWAP: {round(vwap,1)}")
            print(f"Signal: {signal} | OI Chg: {oi_change}")
            print(f"PnL: {round(daily_pnl,2)} | Trades: {trade_count}")
            print("---------------------------------")

            # ENTRY
            if signal != "WAIT" and locked_entry == 0 and (now - last_trade_time > COOLDOWN):
                # NOTE: You need a logic to find the exact ATM Option Symbol here
                # For this code, we track the Index Price 'lp'
                locked_entry = lp
                trade_type = "CALL" if "CALL" in signal else "PUT"
                trail_sl = lp - 20 if trade_type == "CALL" else lp + 20
                last_trade_time = now
                print(f"🚀 VIRTUAL ENTRY: {trade_type} @ {locked_entry}")

            # EXIT / TRAILING
            if locked_entry > 0:
                if trade_type == "CALL":
                    pnl = lp - locked_entry
                    trail_sl = max(trail_sl, lp - 20)
                    exit_hit = lp <= trail_sl
                else:
                    pnl = locked_entry - lp
                    trail_sl = min(trail_sl, lp + 20)
                    exit_hit = lp >= trail_sl

                print(f"TRADING {trade_type} | PnL: {round(pnl,2)} | T-SL: {round(trail_sl,2)}")

                if pnl >= 60 or exit_hit:
                    trade_count += 1
                    daily_pnl += pnl
                    print(f"📌 EXIT TRIGGERED @ {lp}")
                    locked_entry = 0
                    trade_type = None

            prev_oi = toi
            prev_price = lp

        time.sleep(2)

if __name__ == "__main__":
    main()
