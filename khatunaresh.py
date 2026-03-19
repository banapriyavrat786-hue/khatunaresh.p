import time, pandas as pd, pytz
from datetime import datetime
import streamlit as st
from api_helper import ShoonyaApiPy

# --- INITIAL SETUP ---
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="MKPV SNIPER PRO", layout="wide")

# --- SESSION STATE ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_data' not in st.session_state: st.session_state.entry_data = {}
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'start_oi' not in st.session_state: st.session_state.start_oi = 0

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
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                toi = int(q.get('toi', 0))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                if st.session_state.start_oi == 0: st.session_state.start_oi = toi
                oi_delta = toi - st.session_state.start_oi

                # --- IMPROVED LOGIC ---
                c_trend, c_sent = (lp > pivot), (lp > pc)
                p_trend, p_sent = (lp < pivot), (lp < pc)
                
                # OI Logic: Call ke liye OI (+) badhna chahiye, Put ke liye OI (-) kam hona (Selling) ya tezi se badhna
                c_oi_ok = (oi_delta > 0) 
                p_oi_ok = (oi_delta < 0) 

                if lp > pivot:
                    score = sum([c_trend, c_sent, c_oi_ok])
                    signal, color = "CALL BUY ✅", "blue"
                else:
                    score = sum([p_trend, p_sent, p_oi_ok])
                    signal, color = "PUT BUY 🔥", "red"
                
                # Safety calculation (Total 3 major checks)
                safety = round((score / 3) * 100)
                curr_time = datetime.now(IST).strftime("%H:%M:%S")

                with placeholder.container():
                    st.title(f"🚀 MKPV ULTRA SNIPER V3 | {curr_time}")
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    m2.metric("SAFETY", f"{safety}%")
                    m3.metric("OI DELTA", oi_delta)
                    m4.metric("PIVOT", pivot)

                    st.subheader("📋 Sniper Logic Checklist")
                    l_call, l_put = st.columns(2)
                    with l_call:
                        st.write(f"**CALL:** {'✅' if c_trend else '❌'} Trend | {'✅' if c_sent else '❌'} Sent | {'✅' if c_oi_ok else '❌'} OI Support")
                    with l_put:
                        st.write(f"**PUT :** {'✅' if p_trend else '❌'} Trend | {'✅' if p_sent else '❌'} Sent | {'✅' if p_oi_ok else '❌'} OI Support")

                    st.markdown(f"<div style='background-color:{color};padding:20px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {signal} ({safety}%)</h1></div>", unsafe_allow_html=True)

                    # --- STRICT TRADE ENGINE (Safety 100% par hi entry) ---
                    if st.session_state.locked_entry == 0 and safety >= 100:
                        st.session_state.locked_entry = lp
                        st.session_state.entry_data = {"type": signal, "safety": safety, "time": curr_time}

                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in st.session_state.entry_data['type']
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.warning(f"⚡ ACTIVE: {st.session_state.entry_data['type']} | Entry: {st.session_state.locked_entry} | P&L: {pnl} pts")
                        
                        if pnl >= 40 or pnl <= -20:
                            res = "Target" if pnl >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            st.session_state.history.append({"Time": curr_time, "Type": st.session_state.entry_data['type'], "Entry Price": st.session_state.locked_entry, "Exit Price": lp, "P&L": pnl, "Safety": f"{safety}%", "Result": res})
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()

                    if st.session_state.history:
                        st.subheader("📜 Today's Trade History (Detailed)")
                        st.table(pd.DataFrame(st.session_state.history))

            time.sleep(2)
        except: time.sleep(2)
