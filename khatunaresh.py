import streamlit as st
import pandas as pd
import time
from datetime import datetime
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'locked_entry' not in st.session_state:
    st.session_state.locked_entry = 0
if 'api_instance' not in st.session_state:
    st.session_state.api_instance = ShoonyaApiPy()
    st.session_state.logged_in = False

api = st.session_state.api_instance

# --- FETCH DATA ---
def fetch_data(token):
    try:
        q = api.get_quotes(exchange="NSE", token=token)
        if not q or 'lp' not in q: return None
        lp, pc = float(q['lp']), float(q.get('c', q['lp']))
        toi, vol = int(q.get('toi', 0)), int(q.get('v', 0))
        high, low = float(q.get('h', lp)), float(q.get('l', lp))
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if hist and isinstance(hist, list) and len(hist) > 10:
            df = pd.DataFrame(hist)
            df['intc'] = df['intc'].astype(float)
            sma = round(df['intc'].tail(10).mean(), 2)
            pivot = round((high + low + pc) / 3, 2)
            r1 = round((2 * pivot) - low, 2)
            s1 = round((2 * pivot) - high, 2)
            return lp, pc, sma, toi, vol, s1, r1, pivot
        return None
    except: return None

# --- UI SETTINGS ---
st.set_page_config(page_title="GRK WARRIOR V3", layout="wide")
st.title("🚀 MKPV ULTRA SNIPER V3")

# Sidebar
with st.sidebar:
    idx = st.radio("Select Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx == "NIFTY" else "26009"
    totp = st.text_input("Enter TOTP", type="password")
    if st.button("Login"):
        res = api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if res: 
            st.session_state.logged_in = True
            st.success("Logged In!")

if st.session_state.logged_in:
    placeholder = st.empty()
    start_oi = 0

    while True:
        data = fetch_data(token)
        if data:
            lp, pc, sma, toi, vol, s1, r1, pivot = data
            if start_oi == 0: start_oi = toi
            
            # --- AAPKA ORIGINAL LOGIC ---
            c_trend, c_sent = (lp > sma), (lp > pc)
            c_oi = (toi >= start_oi) if toi > 0 else True 
            c_vol = (vol > 0) if vol > 0 else True
            p_trend, p_sent = (lp < sma), (lp < pc)
            p_oi = (toi >= start_oi) if toi > 0 else True
            p_vol = (vol > 0) if vol > 0 else True

            c_score = sum([c_trend, c_sent, c_oi, c_vol])
            p_score = sum([p_trend, p_sent, p_oi, p_vol])

            if c_score >= 3 and lp > sma:
                status, safety = "CALL BUY ✅", round((c_score/4)*100, 1)
            elif p_score >= 3 and lp < sma:
                status, safety = "PUT BUY 🔥", round((p_score/4)*100, 1)
            else:
                status, safety = "SCANNING 📡", 0.0

            def icon(v): return "✅" if v else "❌"

            # --- DISPLAY DASHBOARD ---
            with placeholder.container():
                # Top Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("LTP", lp)
                m2.metric("SMA (10)", sma)
                m3.metric("SAFETY", f"{safety}%")
                m4.metric("PIVOT", pivot)

                st.divider()

                # CHECKLIST SECTION (Wapas add kiya gaya hai)
                st.subheader("📋 Original Logic Checklist")
                col_c, col_p = st.columns(2)
                
                with col_c:
                    st.markdown(f"**CALL:** Trend {icon(c_trend)} | Sent {icon(c_sent)} | OI {icon(c_oi)} | Vol {icon(c_vol)}")
                with col_p:
                    st.markdown(f"**PUT:** Trend {icon(p_trend)} | Sent {icon(p_sent)} | OI {icon(p_oi)} | Vol {icon(p_vol)}")
                
                st.info(f"📡 LEVELS: S1: {s1} | R1: {r1}")
                st.subheader(f"SIGNAL: {status}")

                # Trade Management
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    st.session_state.locked_entry = lp
                    st.session_state.trade_type = status

                if st.session_state.locked_entry > 0:
                    entry = st.session_state.locked_entry
                    is_call = "CALL" in st.session_state.trade_type
                    pnl = round(lp - entry if is_call else entry - lp, 2)
                    sl = round(entry - 20 if is_call else entry + 20, 2)
                    tgt = round(entry + 40 if is_call else entry - 40, 2)

                    st.success(f"🚀 ACTIVE TRADE | ENTRY: {entry} | SL: {sl} | TGT: {tgt}")
                    st.warning(f"💰 LIVE P&L: {pnl} Points")

                    if pnl >= 40 or pnl <= -20:
                        st.session_state.trade_history.append({
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Type": st.session_state.trade_type,
                            "Entry": entry, "Exit": lp, "P&L": pnl
                        })
                        st.session_state.locked_entry = 0

                # History
                if st.session_state.trade_history:
                    st.divider()
                    st.subheader("📜 Historical Trades")
                    st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

        time.sleep(2)
