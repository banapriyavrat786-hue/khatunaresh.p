import streamlit as st
import pandas as pd
import time
from api_helper import ShoonyaApiPy

# --- 1. SESSION STATE (Important for Trading) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'running' not in st.session_state: st.session_state.running = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'target_count' not in st.session_state: st.session_state.target_count = 0
if 'sl_count' not in st.session_state: st.session_state.sl_count = 0
if 'trade_history' not in st.session_state: st.session_state.trade_history = []

# --- 2. UI SETUP ---
st.set_page_config(page_title="Sniper V2 Live", layout="wide")
st.title("🎯 GRK WARRIOR: SNIPER V2")

with st.sidebar:
    st.header("🔐 Auth")
    totp = st.text_input("Fresh TOTP", type="password")
    idx_choice = st.selectbox("Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx_choice == "NIFTY" else "26009"
    
    if st.button("🚀 Login"):
        # Yahan aapka USER, PWD, VC, KEY wala login logic aayega
        st.success("API Connected!")

    st.divider()
    if st.button("▶️ START BOT"): st.session_state.running = True
    if st.button("🛑 STOP BOT"): 
        st.session_state.running = False
        st.session_state.locked_entry = 0 # Reset on stop

# --- 3. FIXED DASHBOARD SLOTS ---
m_col1, m_col2, m_col3 = st.columns(3)
ltp_p = m_col1.empty()
tgt_p = m_col2.empty()
sl_p = m_col3.empty()

signal_p = st.empty()
check_p = st.empty()
active_p = st.empty()
hist_p = st.empty()

# --- 4. TRADING ENGINE ---
if st.session_state.running:
    while st.session_state.running:
        # NOTE: Yahan fetch_data() real data layega
        # Demo ke liye:
        lp = 23385.0 + (time.time() % 10) # Price movement simulation
        sma, pc = 23370.0, 23375.0
        
        # Logic Check
        c_trend, c_sent = (lp > sma), (lp > pc)
        safety = 100.0 if (c_trend and c_sent) else 0.0
        status = "CALL BUY ✅" if safety >= 75 else "SCANNING 📡"

        # UI Update
        ltp_p.metric("LTP", round(lp, 2))
        tgt_p.metric("TGT Hits", st.session_state.target_count)
        sl_p.metric("SL Hits", st.session_state.sl_count)
        
        signal_p.markdown(f"### Current Signal: {status} ({safety}%)")
        
        with check_p.container():
            c1, c2, c3, c4 = st.columns(4)
            def icon(v): return "✅" if v else "❌"
            c1.write(f"**TREND**\n\n {icon(c_trend)}")
            c2.write(f"**SENT**\n\n {icon(c_sent)}")
            c3.write(f"**OI**\n\n ✅")
            c4.write(f"**VOL**\n\n ✅")

        # --- ENTRY TRIGGER (Critical Fix) ---
        if safety >= 75.0 and st.session_state.locked_entry == 0:
            st.session_state.locked_entry = lp
            st.session_state.trade_type = status
            st.toast(f"🚀 Trade Entered at {lp}")

        # --- MONITORING ACTIVE TRADE ---
        if st.session_state.locked_entry > 0:
            pnl = round(lp - st.session_state.locked_entry, 2)
            active_p.warning(f"🔥 ACTIVE TRADE: {st.session_state.trade_type} | Entry: {st.session_state.locked_entry} | PnL: {pnl} pts")
            
            # Exit Logic
            if pnl >= 40:
                st.session_state.target_count += 1
                st.session_state.trade_history.append(f"TGT ✅ | PnL: {pnl}")
                st.session_state.locked_entry = 0
                st.balloons()
            elif pnl <= -20:
                st.session_state.sl_count += 1
                st.session_state.trade_history.append(f"SL 🛑 | PnL: {pnl}")
                st.session_state.locked_entry = 0

        if st.session_state.trade_history:
            hist_p.write(st.session_state.trade_history[-5:])

        time.sleep(2)
