import streamlit as st
import pandas as pd
import time
from datetime import datetime
from SmartApi import SmartConnect
import pyotp

# --- CONFIG ---
API_KEY = "MT72qa1q"
CLIENT_ID = "P51646259"

# Session State Initialization
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- DATA ENGINE (Angel One) ---

def fetch_data(api, token, idx_name):
    checks = {"LTP": False, "History": False, "OI": False}
    try:
        # 1. Market Data (LTP, OI, Volume)
        # Angel One mein 'FULL' mode se hi OI milta hai
        res = api.getMarketData("FULL", {"nse": [token]})
        
        if res['status'] and res['data']['fetched']:
            val = res['data']['fetched'][0]
            lp = float(val['ltp'])
            pc = float(val['close'])
            toi = int(val['oi'])
            vol = int(val['volume'])
            high, low = float(val['high']), float(val['low'])
            checks["LTP"], checks["OI"] = True, True

            # 2. Historical Data (SMA 10 ke liye)
            hist = api.getCandleData({
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "FIVE_MINUTE",
                "fromdate": datetime.now().strftime("%Y-%m-%d 09:15"),
                "todate": datetime.now().strftime("%Y-%m-%d %H:%M")
            })

            if hist['status'] and len(hist['data']) > 10:
                checks["History"] = True
                df = pd.DataFrame(hist['data'], columns=['date','open','high','low','close','vol'])
                df['close'] = df['close'].astype(float)
                sma = round(df['close'].tail(10).mean(), 2)
                
                # Levels Logic
                pivot = round((high + low + pc) / 3, 2)
                s1 = round(pivot - (0.382 * (high - low)), 2)
                r1 = round(pivot + (0.382 * (high - low)), 2)
                price_up = lp > float(df['close'].iloc[-2])
                
                return (lp, pc, sma, toi, vol, s1, r1, pivot, price_up), checks
        return None, checks
    except:
        return None, checks

# --- UI LAYOUT ---
st.set_page_config(page_title="GRK WARRIOR PRO", layout="wide")
st.title("🚀 MKPV ULTRA SNIPER V3 | ANGEL-ONE LIVE")

with st.sidebar:
    st.header("🔑 Bot Authentication")
    idx_choice = st.radio("Select Index", ["NIFTY", "BANKNIFTY"])
    # Nifty Token: 99926000, BankNifty: 99926009
    token = "99926000" if idx_choice == "NIFTY" else "99926009"
    
    mpin = st.text_input("Enter Angel MPIN", type="password")
    # Humne jo key dhoondi thi wo yahan default daal di hai
    totp_key = st.text_input("TOTP Secret Key", value="W6SCERQJX4RSU6TXECROABI7TA", type="password")
    
    if st.button("Start GRK Warrior"):
        obj = SmartConnect(api_key=API_KEY)
        curr_otp = pyotp.TOTP(totp_key).now()
        res = obj.generateSession(CLIENT_ID, mpin, curr_otp)
        
        if res['status']:
            st.session_state.api = obj
            st.session_state.logged_in = True
            st.success("Bot Connected Successfully!")
        else:
            st.error(f"Login Failed: {res['message']}")

# --- MAIN TRADING ENGINE ---
if st.session_state.logged_in:
    api = st.session_state.api
    placeholder = st.empty()
    start_oi = 0

    while True:
        data_bundle, data_checks = fetch_data(api, token, idx_choice)
        
        with placeholder.container():
            st.subheader("🛠️ Data Pipeline Status")
            c1, c2, c3 = st.columns(3)
            c1.info(f"LTP: {'✅' if data_checks['LTP'] else '❌'}")
            c2.info(f"History: {'✅' if data_checks['History'] else '❌'}")
            c3.info(f"OI Data: {'✅' if data_checks['OI'] else '❌'}")

            if data_bundle:
                lp, pc, sma, toi, vol, s1, r1, pivot, price_up = data_bundle
                if start_oi == 0: start_oi = toi
                
                # Logic (Price + OI Momentum)
                # Agar Price up hai aur OI badh raha hai = Bullish
                c_mom = (price_up and toi > start_oi) 
                p_mom = (not price_up and toi > start_oi)
                
                c_score = sum([(lp > sma), (lp > pc), c_mom])
                p_score = sum([(lp < sma), (lp < pc), p_mom])

                if c_score >= 2 and lp > sma: status, safety = "CALL BUY ✅", 80.0
                elif p_score >= 2 and lp < sma: status, safety = "PUT BUY 🔥", 80.0
                else: status, safety = "SCANNING 📡", 0.0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("LTP", lp, delta=round(lp-pc, 2))
                m2.metric("SMA (10)", sma)
                m3.metric("OI", toi)
                m4.metric("SIGNAL", status)

                st.info(f"🎯 LEVELS | Support: {s1} | Resistance: {r1} | Pivot: {pivot}")

                # Trade Locking Logic
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    st.session_state.locked_entry = lp
                    st.session_state.trade_type = status

                if st.session_state.locked_entry > 0:
                    pnl = round(lp - st.session_state.locked_entry if "CALL" in st.session_state.trade_type else st.session_state.locked_entry - lp, 2)
                    st.warning(f"🚀 ACTIVE TRADE | Entry: {st.session_state.locked_entry} | P&L: {pnl} pts")
                    
                    if pnl >= 30 or pnl <= -15: # Target/Stoploss
                        st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M"), "Type": st.session_state.trade_type, "P&L": pnl})
                        st.session_state.locked_entry = 0

            time.sleep(2)
