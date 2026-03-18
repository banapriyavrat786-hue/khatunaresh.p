import time, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP ---
st.set_page_config(page_title="MKPV ULTRA SNIPER V3", layout="wide")

# --- SESSION STATE (Initialization) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_type' not in st.session_state: st.session_state.entry_type = ""
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []

# --- LOGIN UI ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - LOGIN")
    USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
    idx_choice = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    
    if st.button("Start Auto-Bot 🚀"):
        with st.spinner("Connecting..."):
            ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
            if ret and ret.get('stat') == 'Ok':
                st.session_state.logged_in = True
                st.session_state.token = "26000" if idx_choice == "NIFTY" else "26009"
                st.rerun()
            else:
                st.error("Login Failed! Check TOTP.")

# --- MAIN DASHBOARD ---
else:
    # Sidebar ko static rakhein taaki wo na kappe
    st.sidebar.title("📊 Market Stats")
    st.sidebar.success(f"🎯 Targets: {st.session_state.stats['Target']}")
    st.sidebar.error(f"🛑 SL Hits: {st.session_state.stats['SL']}")
    if st.sidebar.button("Logout 🛑"):
        st.session_state.logged_in = False
        st.rerun()

    # Main area ke liye ek container
    main_placeholder = st.empty()

    # --- LIVE LOOP ---
    # Hum while loop ko hata kar rerun ko control karenge
    try:
        q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
        
        if q and 'lp' in q:
            lp = float(q['lp'])
            pc = float(q.get('c', lp))
            high, low = float(q.get('h', lp)), float(q.get('l', lp))
            pivot = round((high + low + pc) / 3, 2)
            
            trend = lp > pivot
            safety = 100 if (lp > pivot + 5 or lp < pivot - 5) else 75
            signal = "CALL BUY ✅" if trend else "PUT BUY 🔥"
            color = "blue" if trend else "red"

            with main_placeholder.container():
                st.title("🚀 MKPV ULTRA SNIPER V3")
                
                # Metrics Row
                m1, m2, m3 = st.columns(3)
                m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                m2.metric("SAFETY", f"{safety}%")
                m3.metric("PIVOT", f"{pivot}")

                # Signal Box
                st.markdown(f"<div style='background-color:{color};padding:20px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {signal}</h1></div>", unsafe_allow_html=True)
                
                # Auto Entry Logic
                if st.session_state.locked_entry == 0 and safety >= 75:
                    st.session_state.locked_entry = lp
                    st.session_state.entry_type = signal

                # Trade Monitoring
                if st.session_state.locked_entry > 0:
                    is_call = "CALL" in st.session_state.entry_type
                    pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                    st.warning(f"⚡ ACTIVE TRADE | ENTRY: {st.session_state.locked_entry} | P&L: {pnl} pts")
                    
                    if pnl >= 40 or pnl <= -20:
                        res = "Target" if pnl >= 40 else "SL"
                        st.session_state.stats[res] += 1
                        st.session_state.history.append({"Time": time.strftime("%H:%M:%S"), "Type": st.session_state.entry_type, "P&L": pnl})
                        st.session_state.locked_entry = 0
                        if pnl >= 40: st.balloons()

                # History Table
                if st.session_state.history:
                    st.subheader("📜 Today's Log")
                    st.table(pd.DataFrame(st.session_state.history).tail(5))
        else:
            main_placeholder.error("🔄 Waiting for Live Data... Refreshing in 3s")

    except Exception as e:
        st.error(f"❌ System Error: {e}")

    # --- REFRESH CONTROL (Blinking Fix) ---
    time.sleep(3) # Ise 3 second kar diya hai taaki blinking kam ho
    st.rerun()
