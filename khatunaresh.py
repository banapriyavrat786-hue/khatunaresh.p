import time, pandas as pd, pytz
from datetime import datetime
import streamlit as st
from api_helper import ShoonyaApiPy

# --- TIMEZONE SETUP (India Time Fix) ---
IST = pytz.timezone('Asia/Kolkata')

# --- PAGE SETUP ---
st.set_page_config(page_title="MKPV SNIPER PRO", layout="wide")

# --- SESSION STATE ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_data' not in st.session_state: st.session_state.entry_data = {}
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'start_oi' not in st.session_state: st.session_state.start_oi = 0

# --- LOGIN UI ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - IST LOGIN")
    USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
    idx = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    if st.button("Launch Pro Dashboard 🚀"):
        ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if ret and ret.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.session_state.token = "26000" if idx == "NIFTY" else "26009"
            st.rerun()
else:
    # Sidebar
    with st.sidebar:
        st.header("📊 Performance")
        st.success(f"🎯 Targets: {st.session_state.stats['Target']}")
        st.error(f"🛑 SL Hits: {st.session_state.stats['SL']}")
        if st.button("Logout 🛑"):
            st.session_state.logged_in = False
            st.rerun()

    placeholder = st.empty()

    while True:
        try:
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                toi = int(q.get('toi', 0))
                vol = int(q.get('v', 0))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                if st.session_state.start_oi == 0: st.session_state.start_oi = toi
                
                # --- ADVANCED LOGIC (OI Fixed for both sides) ---
                c_trend, c_sent = (lp > pivot), (lp > pc)
                p_trend, p_sent = (lp < pivot), (lp < pc)
                
                # OI Logic: Call ke liye OI badhna (Buying), Put ke liye OI ghatna ya badhna logic fix
                oi_ok = (toi >= st.session_state.start_oi) if toi > 0 else True
                vol_ok = (vol > 0)

                c_score = sum([c_trend, c_sent, oi_ok, vol_ok])
                p_score = sum([p_trend, p_sent, oi_ok, vol_ok])
                
                if c_score >= 3 and lp > pivot:
                    signal, color, safety = "CALL BUY ✅", "blue", round((c_score/4)*100)
                elif p_score >= 3 and lp < pivot:
                    signal, color, safety = "PUT BUY 🔥", "red", round((p_score/4)*100)
                else:
                    signal, color, safety = "SCANNING 📡", "grey", 0

                current_time = datetime.now(IST).strftime("%H:%M:%S")

                with placeholder.container():
                    st.title(f"🚀 MKPV ULTRA SNIPER V3 | {current_time}")
                    
                    # 1. Metrics
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    m2.metric("SAFETY", f"{safety}%")
                    m3.metric("OI", toi)
                    m4.metric("PIVOT", pivot)

                    # 2. Logic Checklist (Put OI fixed)
                    st.subheader("📋 Sniper Logic Checklist")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**CALL Checks:**")
                        st.write(f"{'✅' if c_trend else '❌'} Trend | {'✅' if c_sent else '❌'} Sent | {'✅' if oi_ok else '❌'} OI Support")
                    with col2:
                        st.write("**PUT Checks:**")
                        st.write(f"{'✅' if p_trend else '❌'} Trend | {'✅' if p_sent else '❌'} Sent | {'✅' if oi_ok else '❌'} OI Support")

                    # 3. Signal Box
                    st.markdown(f"<div style='background-color:{color};padding:20px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {signal}</h1></div>", unsafe_allow_html=True)

                    # 4. Trade Engine
                    if st.session_state.locked_entry == 0 and safety >= 75:
                        st.session_state.locked_entry = lp
                        st.session_state.entry_data = {"type": signal, "safety": safety, "time": current_time}

                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in st.session_state.entry_data['type']
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.info(f"⚡ ACTIVE: {st.session_state.entry_data['type']} | Entry: {st.session_state.locked_entry} | P&L: {pnl}")
                        
                        if pnl >= 40 or pnl <= -20:
                            res = "Target" if pnl >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            st.session_state.history.append({
                                "Time": st.session_state.entry_data['time'],
                                "Type": st.session_state.entry_data['type'],
                                "Entry": st.session_state.locked_entry,
                                "Exit": lp,
                                "Safety": f"{st.session_state.entry_data['safety']}%",
                                "P&L": pnl,
                                "Result": "🎯" if pnl >= 40 else "🛑"
                            })
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()

                    # 5. Full History Table
                    if st.session_state.history:
                        st.subheader("📜 Today's Detailed Trade Log")
                        st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True)

            time.sleep(2)
        except: time.sleep(2)
