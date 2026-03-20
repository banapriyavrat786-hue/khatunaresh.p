import streamlit as st
import pandas as pd
import time
from datetime import datetime
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# Session State Initialization (Data save karne ke liye)
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'locked_entry' not in st.session_state:
    st.session_state.locked_entry = 0
if 'api_instance' not in st.session_state:
    st.session_state.api_instance = ShoonyaApiPy()
    st.session_state.logged_in = False

api = st.session_state.api_instance

# --- FUNCTIONS ---
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
            sma = round(df['intc'].tail(10).mean(), 2)
            pivot = round((high + low + pc) / 3, 2)
            r1 = round((2 * pivot) - low, 2)
            s1 = round((2 * pivot) - high, 2)
            return lp, pc, sma, toi, vol, s1, r1, pivot
        return None
    except: return None

# --- UI LAYOUT ---
st.set_page_config(page_title="GRK WARRIOR V3", layout="wide")
st.title("🚀 MKPV ULTRA SNIPER V3")

# Sidebar for Login
with st.sidebar:
    idx = st.radio("Select Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx == "NIFTY" else "26009"
    totp = st.text_input("Enter TOTP", type="password")
    if st.button("Login"):
        res = api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if res: 
            st.session_state.logged_in = True
            st.success("Logged In!")

if st.session_state.logged_in:
    placeholder = st.empty()
    start_oi = 0

    while True:
        data = fetch_data(token)
        if data:
            lp, pc, sma, toi, vol, s1, r1, pivot = data
            if start_oi == 0: start_oi = toi
            
            # --- SAME LOGIC (Unchanged) ---
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

            # --- DISPLAY DASHBOARD ---
            with placeholder.container():
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("LTP", lp)
                col2.metric("SMA (10)", sma)
                col3.metric("SAFETY", f"{safety}%")
                col4.metric("PIVOT", pivot)

                st.subheader(f"SIGNAL: {status}")
                
                # Trade Execution Logic
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    st.session_state.locked_entry = lp
                    st.session_state.trade_type = status

                if st.session_state.locked_entry > 0:
                    entry = st.session_state.locked_entry
                    is_call = "CALL" in st.session_state.trade_type
                    pnl = round(lp - entry if is_call else entry - lp, 2)
                    sl = round(entry - 20 if is_call else entry + 20, 2)
                    tgt = round(entry + 40 if is_call else entry - 40, 2)

                    st.info(f"🚀 ACTIVE TRADE | ENTRY: {entry} | SL: {sl} | TGT: {tgt}")
                    st.warning(f"💰 LIVE P&L: {pnl} Points")

                    # Exit Logic & History Save
                    if pnl >= 40 or pnl <= -20:
                        st.session_state.trade_history.append({
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Type": st.session_state.trade_type,
                            "Entry": entry,
                            "Exit": lp,
                            "P&L": pnl
                        })
                        st.session_state.locked_entry = 0

                # History Table
                if st.session_state.trade_history:
                    st.divider()
                    st.subheader("📜 Historical Trades")
                    st.table(pd.DataFrame(st.session_state.trade_history))

        time.sleep(2)
