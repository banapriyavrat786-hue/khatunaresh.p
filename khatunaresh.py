import time, os, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP (Mobile View) ---
st.set_page_config(page_title="GRK SNIPER", layout="centered")
st.title("🏹 MKPV SNIPER V2")

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# Session State for Login and Trade
if 'api' not in st.session_state:
    st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'locked_entry' not in st.session_state:
    st.session_state.locked_entry = 0

# --- LOGIN UI ---
if not st.session_state.logged_in:
    st.subheader("🔑 Broker Login")
    idx_choice = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    
    if st.button("Start Bot 🚀"):
        with st.spinner("Connecting to Shoonya..."):
            ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
            if ret and ret.get('stat') == 'Ok':
                st.session_state.logged_in = True
                st.session_state.token = "26000" if idx_choice == "NIFTY" else "26009"
                st.success("Login Successful!")
                st.rerun()
            else:
                st.error(f"Login Failed: {ret.get('emsg', 'Unknown Error')}")
else:
    # --- DASHBOARD UI ---
    placeholder = st.empty()
    
    if st.button("Stop & Logout 🛑"):
        st.session_state.logged_in = False
        st.rerun()

    while True:
        try:
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                
                # Simple Logic for Dashboard Demo
                pivot = round((high + low + pc) / 3, 2)
                r1 = round((2 * pivot) - low, 2)
                s1 = round((2 * pivot) - high, 2)
                
                with placeholder.container():
                    # Top Metrics
                    c1, c2 = st.columns(2)
                    c1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    c2.metric("PIVOT", f"{pivot}")
                    
                    # Signal Card
                    status = "CALL BUY ✅" if lp > pivot else "PUT BUY 🔥"
                    st.info(f"SIGNAL: **{status}**")
                    
                    # Levels Table
                    st.write(f"📡 **LEVELS:** S1: `{s1}` | R1: `{r1}`")
                    
                    # Trade Logic
                    if st.session_state.locked_entry > 0:
                        pnl = round(lp - st.session_state.locked_entry, 2)
                        st.warning(f"🚀 ACTIVE TRADE | ENTRY: {st.session_state.locked_entry}")
                        st.metric("LIVE P&L", f"{pnl} Pts")
                        if pnl >= 40 or pnl <= -20: 
                            st.session_state.locked_entry = 0
                    elif st.button("Manual Entry 🎯"):
                        st.session_state.locked_entry = lp
            
            time.sleep(2) # Refresh Rate
        except Exception as e:
            st.error(f"Error: {e}")
            break
