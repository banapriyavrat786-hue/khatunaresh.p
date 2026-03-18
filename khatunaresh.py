import time, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP ---
st.set_page_config(page_title="MKPV SNIPER PRO", layout="wide")

# --- SESSION STATE ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []

# --- LOGIN ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - LOGIN")
    USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
    idx = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    if st.button("Launch Dashboard 🚀"):
        ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if ret and ret.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.session_state.token = "26000" if idx == "NIFTY" else "26009"
            st.rerun()
else:
    # --- DASHBOARD UI ---
    st.sidebar.title("📊 Market Stats")
    st.sidebar.success(f"🎯 Targets: {st.session_state.stats['Target']}")
    st.sidebar.error(f"🛑 SL Hits: {st.session_state.stats['SL']}")
    if st.sidebar.button("Logout 🛑"):
        st.session_state.logged_in = False
        st.rerun()

    # Fixed Container for Live Data
    main_view = st.empty()

    # AUTO-REFRESH ALTERNATIVE (No st.rerun blinking)
    while True:
        try:
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                # --- TRADE LOGIC CHECKLIST ---
                trend_ok = lp > pivot
                sent_ok = lp > pc
                safety = 100 if (trend_ok == sent_ok) else 50
                signal = "CALL BUY ✅" if trend_ok else "PUT BUY 🔥"
                color = "blue" if trend_ok else "red"

                with main_view.container():
                    st.title("🚀 MKPV ULTRA SNIPER V3")
                    
                    # 1. Main Metrics
                    c1, c2, c3 = st.columns(3)
                    c1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    c2.metric("SAFETY", f"{safety}%")
                    c3.metric("PIVOT", f"{pivot}")

                    # 2. Checklist & Signal
                    col_logic, col_signal = st.columns([1, 2])
                    with col_logic:
                        st.subheader("📋 Trade Logic")
                        st.write(f"{'✅' if trend_ok else '❌'} Trend (LTP > Pivot)")
                        st.write(f"{'✅' if sent_ok else '❌'} Sentiment (LTP > PC)")
                    
                    with col_signal:
                        st.markdown(f"<div style='background-color:{color};padding:30px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {signal}</h1></div>", unsafe_allow_html=True)

                    # 3. Active Trade & Points Covered
                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in signal
                        points = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.info(f"⚡ ACTIVE TRADE | Entry: {st.session_state.locked_entry} | **Points Covered: {points}**")
                        
                        # Auto Exit
                        if points >= 40 or points <= -20:
                            res = "Target" if points >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            st.session_state.history.append({"Time": time.strftime("%H:%M:%S"), "Type": signal, "P&L": points})
                            st.session_state.locked_entry = 0
                            if points >= 40: st.balloons()
                    
                    elif safety >= 75:
                        st.session_state.locked_entry = lp
                        st.toast(f"🚀 Auto Entry at {lp}")

                    # 4. History Log
                    if st.session_state.history:
                        st.subheader("📜 Today's Log")
                        st.table(pd.DataFrame(st.session_state.history).tail(5))
            
            time.sleep(2) # Natural delay
        except Exception as e:
            st.error(f"Waiting for Data... {e}")
            time.sleep(2)
