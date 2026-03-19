import time, pandas as pd, pytz, numpy as np
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
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []
if 'start_oi' not in st.session_state: st.session_state.start_oi = 0

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
    # --- DASHBOARD UI ---
    st.sidebar.title("📊 Performance")
    st.sidebar.success(f"🎯 Targets: {st.session_state.stats['Target']}")
    st.sidebar.error(f"🛑 SL Hits: {st.session_state.stats['SL']}")
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
                toi = int(q.get('toi', 0))
                vol = int(q.get('v', 0))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                pivot = round((high + low + pc) / 3, 2)
                
                if st.session_state.start_oi == 0: st.session_state.start_oi = toi

                # --- NEW: VOLATILITY & CONDITION LOGIC ---
                range_pct = round(((high - low) / lp) * 100, 2)
                volatility = "HIGH 🔥" if range_pct > 0.5 else "LOW 🧊" if range_pct < 0.2 else "NORMAL ✅"
                
                # Sideways vs Trending
                buffer = 10 if st.session_state.token == "26000" else 25
                if abs(lp - pivot) < buffer:
                    market_cond, cond_color = "SIDEWAYS 😴", "orange"
                elif lp > pivot:
                    market_cond, cond_color = "BULLISH 🚀", "green"
                else:
                    market_cond, cond_color = "BEARISH 📉", "red"

                # Logic Checklist
                c_trend, c_sent = (lp > pivot), (lp > pc)
                p_trend, p_sent = (lp < pivot), (lp < pc)
                oi_ok = (toi >= st.session_state.start_oi)
                
                # Score & Signal
                score = sum([c_trend if lp > pivot else p_trend, c_sent if lp > pivot else p_sent, oi_ok, vol > 0])
                safety = round((score / 4) * 100)
                
                signal = "CALL BUY ✅" if lp > pivot else "PUT BUY 🔥"
                if "SIDEWAYS" in market_cond: signal, safety = "WAITING 🕒", 0
                color = "blue" if "CALL" in signal else "red" if "PUT" in signal else "orange"

                curr_time = datetime.now(IST).strftime("%H:%M:%S")

                with placeholder.container():
                    st.title(f"🚀 MKPV ULTRA SNIPER V3 | {curr_time}")
                    
                    # 1. Advanced Metrics
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    m2.metric("VOLATILITY", volatility, help=f"Range: {range_pct}%")
                    m3.metric("OI DELTA", toi - st.session_state.start_oi)
                    m4.metric("CONDITION", market_cond)

                    # 2. Daily Range
                    st.write(f"📉 **Day Range:** Low: `{low}` <---> High: `{high}` | **Pivot:** `{pivot}`")

                    # 3. Logic Checklist
                    st.subheader("📋 Sniper Checklist")
                    l1, l2 = st.columns(2)
                    with l1: st.write(f"{'✅' if c_trend else '❌'} CALL Trend | {'✅' if c_sent else '❌'} Sent")
                    with l2: st.write(f"{'✅' if p_trend else '❌'} PUT Trend | {'✅' if p_sent else '❌'} Sent")
                    st.write(f"{'✅' if oi_ok else '❌'} OI Support | {'✅' if vol > 0 else '❌'} Volume")

                    # 4. Signal Box
                    st.markdown(f"<div style='background-color:{color};padding:25px;border-radius:15px;text-align:center'><h1 style='color:white;margin:0;'>SIGNAL: {signal} ({safety}%)</h1></div>", unsafe_allow_html=True)

                    # 5. Trade Tracking
                    if st.session_state.locked_entry == 0 and safety >= 75 and "WAITING" not in signal:
                        st.session_state.locked_entry, st.session_state.entry_type = lp, signal

                    if st.session_state.locked_entry > 0:
                        is_call = "CALL" in st.session_state.entry_type
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.warning(f"⚡ ACTIVE: {st.session_state.entry_type} | Entry: {st.session_state.locked_entry} | P&L: {pnl} pts")
                        
                        if pnl >= 40 or pnl <= -20:
                            res = "Target" if pnl >= 40 else "SL"
                            st.session_state.stats[res] += 1
                            st.session_state.history.append({"Time": curr_time, "Type": st.session_state.entry_type, "P&L": pnl, "Result": res})
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()

                    if st.session_state.history:
                        st.subheader("📜 Today's Log")
                        st.table(pd.DataFrame(st.session_state.history).tail(5))

            time.sleep(2)
        except: time.sleep(2)
