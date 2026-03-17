import time, os, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

st.set_page_config(page_title="GRK SNIPER", layout="centered")
st.title("🏹 MKPV SNIPER V2")

USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# --- SESSION STATE (Data ko yaad rakhne ke liye) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}

if not st.session_state.logged_in:
    # ... (Purana Login UI) ...
    st.subheader("🔑 Broker Login")
    idx_choice = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    if st.button("Start Bot 🚀"):
        ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if ret and ret.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.session_state.token = "26000" if idx_choice == "NIFTY" else "26009"
            st.rerun()
else:
    placeholder = st.empty()
    
    while True:
        try:
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                # --- SAFETY LOGIC ---
                # Maan lijiye aapka checklist logic (LP vs Pivot, LP vs PC)
                c_trend = (lp > pivot)
                c_sent = (lp > pc)
                # Score calculation (Example: 2 parameters)
                safety = round(((c_trend + c_sent) / 2) * 100, 1) if lp > pivot else round((( (lp < pivot) + (lp < pc) ) / 2) * 100, 1)

                with placeholder.container():
                    # 1. Performance Stats
                    s1, s2 = st.columns(2)
                    s1.success(f"🎯 Targets Hit: {st.session_state.stats['Target']}")
                    s2.error(f"🛑 SL Hit: {st.session_state.stats['SL']}")

                    # 2. Live Metrics
                    c1, c2, c3 = st.columns(3)
                    c1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    c2.metric("SAFETY", f"{safety}%")
                    c3.metric("PIVOT", f"{pivot}")

                    # 3. Active Trade Logic
                    if st.session_state.locked_entry > 0:
                        pnl = round(lp - st.session_state.locked_entry, 2)
                        st.warning(f"🚀 ACTIVE TRADE | ENTRY: {st.session_state.locked_entry}")
                        st.metric("LIVE P&L", f"{pnl} Pts", delta=pnl)
                        
                        # Target/SL Auto Tracking
                        if pnl >= 40:
                            st.session_state.stats["Target"] += 1
                            st.session_state.locked_entry = 0
                            st.balloons()
                        elif pnl <= -20:
                            st.session_state.stats["SL"] += 1
                            st.session_state.locked_entry = 0
                    
                    elif safety >= 75: # Auto Entry Example
                        if st.button("Manual Entry 🎯", key="entry_btn"):
                            st.session_state.locked_entry = lp
                    
                    st.button("Logout 🛑", on_click=lambda: st.session_state.update({"logged_in": False}), key="logout_btn")
            
            time.sleep(2)
        except: break
