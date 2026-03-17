import time, os, pandas as pd
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
api = ShoonyaApiPy()
locked_entry = 0

def fetch_data(token):
    try:
        q = api.get_quotes(exchange="NSE", token=token)
        if not q or 'lp' not in q: return None
        
        lp, pc = float(q['lp']), float(q.get('c', q['lp']))
        toi, vol = int(q.get('toi', 0)), int(q.get('v', 0))
        high, low = float(q.get('h', lp)), float(q.get('l', lp))

        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if hist and isinstance(hist, list) and len(hist) > 10:
            df = pd.DataFrame(hist)
            df['intc'] = df['intc'].astype(float)
            
            # SMA Calculation
            sma = round(df['intc'].tail(10).mean(), 2)
            
            # --- PIVOT LEVELS ---
            pivot = round((high + low + pc) / 3, 2)
            r1 = round((2 * pivot) - low, 2)
            s1 = round((2 * pivot) - high, 2)
            
            return lp, pc, sma, toi, vol, s1, r1, pivot
        return None
    except: return None

def main():
    global locked_entry
    idx = input("1. NIFTY  2. BANKNIFTY: ")
    token = "26000" if idx == "1" else "26009"
    
    totp = input("Enter Fresh TOTP: ").strip()
    api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")

    start_oi = 0

    while True:
        data = fetch_data(token)
        if data:
            lp, pc, sma, toi, vol, s1, r1, pivot = data
            if start_oi == 0: start_oi = toi
            
            # --- SMART CHECKLIST ---
            # Agar OI/Vol available nahi hai (0 hai), toh unhe auto-pass karega
            c_trend, c_sent = (lp > sma), (lp > pc)
            c_oi = (toi >= start_oi) if toi > 0 else True 
            c_vol = (vol > 0) if vol > 0 else True

            p_trend, p_sent = (lp < sma), (lp < pc)
            p_oi = (toi >= start_oi) if toi > 0 else True
            p_vol = (vol > 0) if vol > 0 else True

            c_score = sum([c_trend, c_sent, c_oi, c_vol])
            p_score = sum([p_trend, p_sent, p_oi, p_vol])

            if c_score >= 3 and lp > sma:
                status, safety = "CALL BUY ✅", round((c_score/4)*100, 1)
            elif p_score >= 3 and lp < sma:
                status, safety = "PUT BUY 🔥", round((p_score/4)*100, 1)
            else:
                status, safety = "SCANNING 📡", 0.0

            os.system("clear")
            print(f"========== GRK WARRIOR: SNIPER V2 ==========")
            print(f"LTP: {lp} | PIVOT: {pivot} | SIGNAL: {status}")
            print(f"SAFETY: {safety}%")
            print(f"---------------------------------------------")
            
            def icon(v): return "✅" if v else "❌"
            print(f"      [TREND] [SENTIMENT] [OI] [VOL]")
            print(f"CALL:   {icon(c_trend)}        {icon(c_sent)}        {icon(c_oi)}    {icon(c_vol)}")
            print(f"PUT :   {icon(p_trend)}        {icon(p_sent)}        {icon(p_oi)}    {icon(p_vol)}")
            print(f"---------------------------------------------")
            print(f"📡 LEVELS: S1: {s1} | R1: {r1}")
            print(f"---------------------------------------------")
            
            if safety >= 75.0 and locked_entry == 0:
                locked_entry = lp

            if locked_entry > 0:
                pnl = round(lp - locked_entry if (lp > sma) else locked_entry - lp, 2)
                print(f"🚀 ACTIVE TRADE! | ENTRY: {locked_entry}")
                print(f"💰 LIVE P&L: {pnl} Pts")
                print(f"🛑 SL: {round(locked_entry-20 if lp > sma else locked_entry+20, 2)}")
                print(f"🎯 TGT: {round(locked_entry+40 if lp > sma else locked_entry-40, 2)}")
                if pnl >= 40 or pnl <= -20: locked_entry = 0 
        
        time.sleep(3)

if __name__ == "__main__": main()
