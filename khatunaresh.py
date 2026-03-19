import time, pandas as pd, pytz
from datetime import datetime
import streamlit as st
from api_helper import ShoonyaApiPy

# --- 1. INITIAL SETUP ---
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="MKPV SNIPER PRO", layout="wide")

# --- 2. SESSION STATE (Data Persistence Fix) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_data' not in st.session_state: st.session_state.entry_data = {}
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'start_oi' not in st.session_state: st.session_state.start_oi = 0

# --- 3. LOGIN LOGIC ---
if not st.session_state.logged_in:
    st.title("🏹 MKPV SNIPER - LOGIN")
    USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"
    idx = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    if st.button("Launch Advanced Dashboard 🚀"):
        ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if ret and ret.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.session_state.token = "26000" if idx == "NIFTY" else "26009"
            st.rerun()
else:
    # --- SIDEBAR STATS ---
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
                vol = int(q.get('v', 0))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                if st.session_state.start_oi == 0: st.session_state.start_oi = toi
                
                # Logic Score
                c_trend, c_sent = (lp > pivot), (lp > pc)
                p_trend, p_sent = (lp < pivot), (lp < pc)
                oi_ok = (toi >= st.session_state.start_oi)
                
                score = sum([c_trend if lp > pivot else p_trend, c_sent if lp > pivot else p_sent, oi_ok, vol > 0])
                safety = round((score / 4) * 100)
                
                signal = "CALL BUY ✅" if lp > pivot else "PUT BUY 🔥"
                color = "blue" if lp > pivot else "red"
                curr_time = datetime.now(IST).strftime("%H:%M:%S")

                with placeholder.container():
                    st.title(f"🚀 MKPV ULTRA SNIPER V3 | {curr_time}")
                    
                    # 1. Dashboard Metrics
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    m2.metric("SAFETY", f"{safety}%")
                    m3.metric("OI DELTA", toi - st.session_state.start_oi)
                    m4.metric("PIVOT", pivot)

                    # 2. Logic Checklist (Side-by-Side)
                    st.subheader("📋 Sniper Logic Checklist")
                    l_call, l_put = st.columns(2)
                    with l_call:
                        st.write("**CALL Side Logic:**")
                        st.write(f"{'✅' if c_trend else '❌'} Price > Pivot | {'✅' if c_sent else '❌'} Price > PC")
                    with l_put:
                        st.write("**PUT Side Logic:**")
                        st.write(f"{'✅' if p_trend else '❌'} Price < Pivot | {'✅' if p_sent else '❌'} Price < PC")

                    # 3. Big Signal Box
                    st.markdown(f"<div style='background-color:{color};padding:20px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {signal} ({safety}%)</h1></div>", unsafe_allow_html=True)

                    # 4. ACTIVE TRADE MONITOR
                    if st.session_state.locked_entry == 0 and safety >= 75:
                        st.session_state.locked_entry = lp
                        st.session_state.entry_data = {"type": signal, "safety": safety, "time": curr_time}

                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in st.session_state.entry_data['type']
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.warning(f"⚡ ACTIVE: {st.session_state.entry_data['type']} | Entry: {st.session_state.locked_entry} | P&L: {pnl} pts")
                        
                        if pnl >= 40 or pnl <= -20:
                            res = "Target" if pnl >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            # Yahan history mein saari details add ho rahi hain
                            st.session_state.history.append({
                                "Time": st.session_state.entry_data['time'],
                                "Type": st.session_state.entry_data['type'],
                                "Entry Price": st.session_state.locked_entry,
                                "Exit Price": lp,
                                "Points (P&L)": pnl,
                                "Safety %": f"{st.session_state.entry_data['safety']}%",
                                "Result": "✅ Target" if pnl >= 40 else "❌ SL"
                            })
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()

                    # 5. HISTORICAL TRADE LOG (Detailed Table)
                    if st.session_state.history:
                        st.divider()
                        st.subheader("📜 Today's Trade History (Details)")
                        # Table ko full width aur detailed banaya gaya hai
                        df_history = pd.DataFrame(st.session_state.history)
                        st.table(df_history)

            time.sleep(2)
        except: time.sleep(2)
