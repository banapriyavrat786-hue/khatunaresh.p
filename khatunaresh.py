import time, os, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP ---
st.set_page_config(page_title="GRK SNIPER", layout="centered")
st.title("🏹 MKPV SNIPER V3")

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# --- SESSION STATE ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}

if not st.session_state.logged_in:
    st.subheader("🔑 Broker Login")
    idx_choice = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    
    if st.button("Start Bot 🚀"):
        with st.spinner("Connecting..."):
            ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
            if ret and ret.get('stat') == 'Ok':
                st.session_state.logged_in = True
                st.session_state.token = "26000" if idx_choice == "NIFTY" else "26009"
                st.rerun()
            else:
                st.error("Login Failed! Check TOTP.")
else:
    # Logout Button at Top Right
    if st.sidebar.button("Logout 🛑"):
        st.session_state.logged_in = False
        st.rerun()

    placeholder = st.empty()
    
    while True:
        try:
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                # --- SIGNAL & SAFETY LOGIC ---
                if lp > pivot:
                    status, color, safety = "CALL BUY ✅", "blue", 100.0 if lp > (pivot + 5) else 75.0
                else:
                    status, color, safety = "PUT BUY 🔥", "red", 100.0 if lp < (pivot - 5) else 75.0

                with placeholder.container():
                    # 1. Stats Row
                    s1, s2 = st.columns(2)
                    s1.success(f"🎯 Targets: {st.session_state.stats['Target']}")
                    s2.error(f"🛑 SL Hit: {st.session_state.stats['SL']}")

                    # 2. Main Metrics
                    st.divider()
                    m1, m2, m3 = st.columns(3)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    m2.metric("SAFETY", f"{safety}%")
                    m3.metric("PIVOT", f"{pivot}")

                    # 3. SIGNAL BOX (Ab Ye Saaf Dikhega)
                    st.markdown(f"""
                    <div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center;">
                        <h1 style="color:white; margin:0;">SIGNAL: {status}</h1>
                    </div>
                    """, unsafe_allow_code=True)
                    
                    st.write(f"📡 **LEVELS:** S1: `{round((2*pivot)-high,2)}` | R1: `{round((2*pivot)-low,2)}`")

                    # 4. Active Trade Tracker
                    if st.session_state.locked_entry > 0:
                        pnl = round(lp - st.session_state.locked_entry if lp > pivot else st.session_state.locked_entry - lp, 2)
                        st.warning(f"🚀 ACTIVE TRADE | ENTRY: {st.session_state.locked_entry}")
                        st.metric("LIVE P&L", f"{pnl} Pts", delta=pnl)
                        
                        if pnl >= 40:
                            st.session_state.stats["Target"] += 1
                            st.session_state.locked_entry = 0
                            st.balloons()
                        elif pnl <= -20:
                            st.session_state.stats["SL"] += 1
                            st.session_state.locked_entry = 0
                    else:
                        if st.button("Take Entry 🎯"):
                            st.session_state.locked_entry = lp
            
            time.sleep(2)
        except Exception as e:
            st.error(f"Connection Lost: {e}")
            break
