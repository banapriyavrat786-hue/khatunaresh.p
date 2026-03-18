import time, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP ---
st.set_page_config(page_title="MKPV SNIPER PRO", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'start_oi' not in st.session_state: st.session_state.start_oi = 0

# --- LOGIN UI ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - SECURE LOGIN")
    USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
    idx = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    if st.button("Launch Advanced Dashboard 🚀"):
        ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if ret and ret.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.session_state.token = "26000" if idx == "NIFTY" else "26009"
            st.rerun()

# --- MAIN DASHBOARD ---
else:
    # Sidebar for logout and daily stats
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
                
                # First time OI capture
                if st.session_state.start_oi == 0: st.session_state.start_oi = toi
                
                # SMA/Trend Logic (Using 5-min Pivot as Trend)
                pivot = round((high + low + pc) / 3, 2)
                
                # --- ADVANCED CHECKLIST LOGIC ---
                # Call Logic
                c_trend = lp > pivot
                c_sent = lp > pc
                c_oi = (toi >= st.session_state.start_oi) if toi > 0 else True
                c_vol = (vol > 0)
                
                # Put Logic
                p_trend = lp < pivot
                p_sent = lp < pc
                p_oi = (toi >= st.session_state.start_oi) if toi > 0 else True
                p_vol = (vol > 0)

                # Score Calculation
                c_score = sum([c_trend, c_sent, c_oi, c_vol])
                p_score = sum([p_trend, p_sent, p_oi, p_vol])
                
                if c_score >= 3 and lp > pivot:
                    signal, color, safety = "CALL BUY ✅", "blue", round((c_score/4)*100)
                elif p_score >= 3 and lp < pivot:
                    signal, color, safety = "PUT BUY 🔥", "red", round((p_score/4)*100)
                else:
                    signal, color, safety = "SCANNING 📡", "grey", 0

                with placeholder.container():
                    st.title("🚀 MKPV ULTRA SNIPER V3")
                    
                    # 1. Main Metrics
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    m2.metric("SAFETY", f"{safety}%")
                    m3.metric("OI", toi)
                    m4.metric("PIVOT", pivot)

                    # 2. Logic Checklist (Clean UI)
                    st.subheader("📋 Sniper Logic Checklist")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**CALL Checks:**")
                        st.write(f"{'✅' if c_trend else '❌'} Trend (LTP > Pivot)")
                        st.write(f"{'✅' if c_sent else '❌'} Sentiment (LTP > PC)")
                        st.write(f"{'✅' if c_oi else '❌'} OI Support")
                    with col2:
                        st.write(f"**PUT Checks:**")
                        st.write(f"{'✅' if p_trend else '❌'} Trend (LTP < Pivot)")
                        st.write(f"{'✅' if p_sent else '❌'} Sentiment (LTP < PC)")
                        st.write(f"{'✅' if p_vol else '❌'} Volume Active")

                    # 3. Big Signal Box
                    st.markdown(f"<div style='background-color:{color};padding:25px;border-radius:15px;text-align:center'><h1 style='color:white;margin:0;'>SIGNAL: {signal}</h1></div>", unsafe_allow_html=True)

                    # 4. Auto Trade Tracker
                    if st.session_state.locked_entry == 0 and safety >= 75:
                        st.session_state.locked_entry = lp
                        st.session_state.entry_type = signal
                        st.toast(f"🎯 Auto Entry at {lp}")

                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in st.session_state.entry_type
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.info(f"⚡ ACTIVE TRADE | Entry: {st.session_state.locked_entry} | **Live P&L: {pnl} Pts**")
                        
                        if pnl >= 40 or pnl <= -20:
                            res = "Target" if pnl >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            st.session_state.history.append({"Time": time.strftime("%H:%M:%S"), "Type": st.session_state.entry_type, "P&L": pnl})
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()

                    # 5. History Log
                    if st.session_state.history:
                        st.subheader("📜 Today's Trades")
                        st.table(pd.DataFrame(st.session_state.history).tail(5))

            time.sleep(2) # Stabilizer delay
        except: time.sleep(2)
