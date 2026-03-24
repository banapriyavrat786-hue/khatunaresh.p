import streamlit as st
import pandas as pd
import time
from datetime import datetime
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# Streamlit autorefresh component ko install karna padega (pip install streamlit-autorefresh)
# Agar install nahi karna chahte toh hum code ko refresh trigger denge.

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'locked_entry' not in st.session_state:
    st.session_state.locked_entry = 0
if 'start_oi' not in st.session_state:
    st.session_state.start_oi = 0
if 'api' not in st.session_state:
    st.session_state.api = ShoonyaApiPy()

api = st.session_state.api

# --- UI SETTINGS ---
st.set_page_config(page_title="GRK WARRIOR V3", layout="wide")
st.title("🚀 MKPV ULTRA SNIPER V3")

with st.sidebar:
    idx = st.radio("Select Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx == "NIFTY" else "26009"
    totp = st.text_input("Enter Fresh TOTP", type="password")
    if st.button("Login"):
        res = api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if res and res.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.rerun() # Refresh screen after login

# --- MAIN ENGINE ---
if st.session_state.logged_in:
    # DATA FETCHING (Logic unchanged)
    q = api.get_quotes(exchange="NSE", token=token)
    if q and 'lp' in q:
        lp, pc = float(q['lp']), float(q.get('c', q['lp']))
        toi, vol = int(q.get('toi', 0)), int(q.get('v', 0))
        high, low = float(q.get('h', lp)), float(q.get('l', lp))
        
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if hist and isinstance(hist, list) and len(hist) > 10:
            df = pd.DataFrame(hist)
            df['intc'] = df['intc'].astype(float)
            sma = round(df['intc'].tail(10).mean(), 2)
            pivot = round((high + low + pc) / 3, 2)
            r1, s1 = round((2 * pivot) - low, 2), round((2 * pivot) - high, 2)

            # Score Calculation
            if st.session_state.start_oi == 0: st.session_state.start_oi = toi
            c_score = sum([(lp > sma), (lp > pc), (toi >= st.session_state.start_oi), (vol > 0)])
            p_score = sum([(lp < sma), (lp < pc), (toi >= st.session_state.start_oi), (vol > 0)])

            # SIGNAL LOGIC
            status = "SCANNING 📡"
            if c_score >= 3 and lp > sma: status = "CALL BUY ✅"
            elif p_score >= 3 and lp < sma: status = "PUT BUY 🔥"
            safety = round(((c_score if "CALL" in status else p_score)/4)*100, 1) if "BUY" in status else 0.0

            # --- UI DISPLAY ---
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("LTP", lp)
            col2.metric("SMA (10)", sma)
            col3.metric("SAFETY", f"{safety}%")
            col4.metric("PIVOT", pivot)

            st.divider()
            st.subheader(f"SIGNAL: {status}")

            # TRADE HANDLER
            if safety >= 75.0 and st.session_state.locked_entry == 0:
                st.session_state.locked_entry = lp
                st.session_state.trade_type = status

            if st.session_state.locked_entry > 0:
                entry = st.session_state.locked_entry
                is_call = "CALL" in st.session_state.trade_type
                pnl = round(lp - entry if is_call else entry - lp, 2)
                st.info(f"🚀 ACTIVE TRADE | ENTRY: {entry} | P&L: {pnl}")
                if pnl >= 40 or pnl <= -20:
                    st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Type": st.session_state.trade_type, "P&L": pnl})
                    st.session_state.locked_entry = 0

            # HISTORY
            if st.session_state.trade_history:
                st.table(pd.DataFrame(st.session_state.trade_history))

    # Yahan magic hai: Ye website ko har 2 second mein refresh karega bina loop ke
    time.sleep(2)
    st.rerun() 
else:
    st.info("Waiting for Login...")
