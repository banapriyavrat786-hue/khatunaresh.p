import time, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP ---
st.set_page_config(page_title="MKPV ULTRA SNIPER V3", layout="wide")

# --- SESSION STATE (Data Storage) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_data' not in st.session_state: st.session_state.entry_data = {}
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'last_update_time' not in st.session_state: st.session_state.last_update_time = time.time()

# --- LOGIN UI ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - SECURE LOGIN")
    USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
    idx_choice = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    
    if st.button("Start Auto-Bot 🚀"):
        with st.spinner("Connecting to Broker..."):
            ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
            if ret and ret.get('stat') == 'Ok':
                st.session_state.logged_in = True
                st.session_state.token = "26000" if idx_choice == "NIFTY" else "26009"
                st.rerun()
            else:
                st.error(f"Login Failed: {ret.get('emsg', 'Check TOTP')}")

# --- MAIN DASHBOARD ---
else:
    st.title("🚀 MKPV ULTRA SNIPER V3")
    
    # Sidebar for Stats & Health
    with st.sidebar:
        st.header("📊 Market Stats")
        st.success(f"🎯 Targets: {st.session_state.stats['Target']}")
        st.error(f"🛑 SL Hits: {st.session_state.stats['SL']}")
        st.divider()
        if st.button("Logout 🛑"):
            st.session_state.logged_in = False
            st.rerun()

    placeholder = st.empty()

    try:
        q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
        
        if q and 'lp' in q:
            # Update Health Timer
            st.session_state.last_update_time = time.time()
            
            lp = float(q['lp'])
            pc = float(q.get('c', lp))
            high, low = float(q.get('h', lp)), float(q.get('l', lp))
            vol = q.get('v', '0')
            oi = q.get('toi', '0')
            
            # --- CALCULATIONS ---
            pivot = round((high + low + pc) / 3, 2)
            r1, s1 = round((2*pivot)-low, 2), round((2*pivot)-high, 2)
            
            trend_ok = lp > pivot
            sent_ok = lp > pc
            safety = 100 if (trend_ok == sent_ok) else 50
            signal = "CALL BUY ✅" if trend_ok else "PUT BUY 🔥"
            color = "blue" if trend_ok else "red"

            with placeholder.container():
                # 1. Top Row Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                m2.metric("SAFETY", f"{safety}%")
                m3.metric("PIVOT", f"{pivot}")

                # 2. Data Health Check
                time_diff = time.time() - st.session_state.last_update_time
                if time_diff > 5:
                    st.error(f"⚠️ DATA LAG: Data is {round(time_diff)}s old!")

                # 3. Signal Box
                st.markdown(f"<div style='background-color:{color};padding:20px;border-radius:10px;text-align:center'><h1 style='color:white;margin:0;'>SIGNAL: {signal}</h1></div>", unsafe_allow_html=True)
                
                st.write(f"📊 **Levels:** S1: `{s1}` | R1: `{r1}` | **Live Data:** OI: `{oi}` | Vol: `{vol}`")

                # 4. Auto-Entry & Trade Tracking
                if st.session_state.locked_entry == 0:
                    if safety >= 75:
                        st.session_state.locked_entry = lp
                        st.session_state.entry_data = {"type": signal, "safety": safety, "time": time.strftime("%H:%M:%S")}
                        st.toast(f"🚀 Auto Entry: {signal} at {lp}")
                else:
                    is_call = "CALL" in st.session_state.entry_data['type']
                    pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                    
                    st.warning(f"⚡ ACTIVE TRADE | ENTRY: {st.session_state.locked_entry} | P&L: {pnl} pts")
                    
                    if pnl >= 40 or pnl <= -20:
                        res = "Target" if pnl >= 40 else "SL"
                        st.session_state.stats[res] += 1
                        st.session_state.history.append({
                            "Time": st.session_state.entry_data['time'],
                            "Type": st.session_state.entry_data['type'],
                            "Safety": f"{st.session_state.entry_data['safety']}%",
                            "Entry": st.session_state.locked_entry,
                            "Exit": lp, "P&L": pnl, "Result": "✅" if pnl >= 40 else "❌"
                        })
                        st.session_state.locked_entry = 0
                        if pnl >= 40: st.balloons()

                # 5. History Table
                if st.session_state.history:
                    st.subheader("📜 Today's Trade Log")
                    st.dataframe(pd.DataFrame(st.session_state.history).tail(10), use_container_width=True)
        else:
            st.error("🚫 Connection Lost: Price data not receiving from Shoonya.")

    except Exception as e:
        st.error(f"❌ Error: {e}")

    # --- AUTO REFRESH ---
    time.sleep(2)
    st.rerun()
