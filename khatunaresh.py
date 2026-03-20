import time, pandas as pd, pytz
from datetime import datetime
import streamlit as st
from api_helper import ShoonyaApiPy

# --- INITIAL SETUP ---
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="MKPV SNIPER PRO", layout="wide")

# --- SESSION STATE (Data Persistence) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'start_oi' not in st.session_state: st.session_state.start_oi = 0

# --- LOGIN UI ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - ORIGINAL LOGIC")
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
    # Sidebar
    with st.sidebar:
        st.header("📊 Performance")
        st.success(f"🎯 Targets: {st.session_state.stats['Target']}")
        st.error(f"🛑 SL Hits: {st.session_state.stats['SL']}")
        if st.button("Logout 🛑"):
            st.session_state.logged_in = False
            st.rerun()

    placeholder = st.empty()

    while st.session_state.logged_in:
        try:
            # --- AAPKA ORIGINAL FETCH LOGIC ---
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            hist = st.session_state.api.get_time_price_series(exchange="NSE", token=st.session_state.token, interval=5)
            
            if q and 'lp' in q and hist:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                toi = int(q.get('toi', 0))
                vol = int(q.get('v', 0))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                
                # SMA Calculation (Exactly as per your code)
                df = pd.DataFrame(hist)
                sma = round(df['intc'].astype(float).tail(10).mean(), 2)
                
                # Pivot Levels (Exactly as per your code)
                pivot = round((high + low + pc) / 3, 2)
                r1 = round((2 * pivot) - low, 2)
                s1 = round((2 * pivot) - high, 2)
                
                if st.session_state.start_oi == 0: st.session_state.start_oi = toi
                
                # --- AAPKA ORIGINAL SMART CHECKLIST ---
                c_trend, c_sent = (lp > sma), (lp > pc)
                c_oi = (toi >= st.session_state.start_oi) if toi > 0 else True 
                c_vol = (vol > 0) if vol > 0 else True

                p_trend, p_sent = (lp < sma), (lp < pc)
                p_oi = (toi >= st.session_state.start_oi) if toi > 0 else True
                p_vol = (vol > 0) if vol > 0 else True

                c_score = sum([c_trend, c_sent, c_oi, c_vol])
                p_score = sum([p_trend, p_sent, p_oi, p_vol])

                if c_score >= 3 and lp > sma:
                    status, color, safety = "CALL BUY ✅", "blue", round((c_score/4)*100, 1)
                elif p_score >= 3 and lp < sma:
                    status, color, safety = "PUT BUY 🔥", "red", round((p_score/4)*100, 1)
                else:
                    status, color, safety = "SCANNING 📡", "grey", 0.0

                curr_time = datetime.now(IST).strftime("%H:%M:%S")

                with placeholder.container():
                    st.title(f"🚀 MKPV ULTRA SNIPER V3 | {curr_time}")
                    
                    # Dashboard Metrics
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-sma, 2))
                    m2.metric("SMA (10)", f"{sma}")
                    m3.metric("SAFETY", f"{safety}%")
                    m4.metric("PIVOT", f"{pivot}")

                    # Logic Checklist Display
                    st.subheader("📋 Original Logic Checklist")
                    l1, l2 = st.columns(2)
                    with l1:
                        st.write(f"**CALL:** {'✅' if c_trend else '❌'} Trend | {'✅' if c_sent else '❌'} Sentiment | {'✅' if c_oi else '❌'} OI | {'✅' if c_vol else '❌'} Vol")
                    with l2:
                        st.write(f"**PUT :** {'✅' if p_trend else '❌'} Trend | {'✅' if p_sent else '❌'} Sentiment | {'✅' if p_oi else '❌'} OI | {'✅' if p_vol else '❌'} Vol")

                    # Signal Box
                    st.markdown(f"<div style='background-color:{color};padding:20px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {status}</h1></div>", unsafe_allow_html=True)
                    st.write(f"📡 **LEVELS:** S1: `{s1}` | R1: `{r1}`")

                    # --- AAPKA ORIGINAL TRADE ENGINE ---
                    if safety >= 75.0 and st.session_state.locked_entry == 0:
                        st.session_state.locked_entry = lp
                        st.session_state.entry_type = status

                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in st.session_state.entry_type
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.warning(f"🚀 ACTIVE TRADE! | Entry: {st.session_state.locked_entry} | Live P&L: {pnl} Pts")
                        
                        # Target/SL as per your code (40/20)
                        if pnl >= 40 or pnl <= -20:
                            res = "Target" if pnl >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            st.session_state.history.append({"Time": curr_time, "Type": st.session_state.entry_type, "Entry": st.session_state.locked_entry, "Exit": lp, "P&L": pnl, "Safety": f"{safety}%"})
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()

                    if st.session_state.history:
                        st.subheader("📜 Today's Log")
                        st.table(pd.DataFrame(st.session_state.history).tail(5))

            time.sleep(3) # Exact 3 second delay as per your code
        except: time.sleep(3)
