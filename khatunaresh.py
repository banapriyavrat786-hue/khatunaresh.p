import streamlit as st
import pandas as pd
import time
import os
from api_helper import ShoonyaApiPy

# --- CONFIG & CREDENTIALS ---
# Aapka diya hua data maine yahan fix kar diya hai
USER = "FN183822"
PWD  = "PSbana@321"
VC   = "FN183822_U"
KEY  = "e6006270e8270b71a12afe278e927f19"

# --- SESSION STATE INITIALIZATION ---
if 'api' not in st.session_state:
    st.session_state.api = ShoonyaApiPy()
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'running' not in st.session_state:
    st.session_state.running = False
if 'locked_entry' not in st.session_state:
    st.session_state.locked_entry = 0
if 'target_count' not in st.session_state:
    st.session_state.target_count = 0
if 'sl_count' not in st.session_state:
    st.session_state.sl_count = 0

# --- FUNCTIONS ---
def fetch_data(token):
    try:
        api = st.session_state.api
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

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sniper V2", layout="wide")
st.title("🎯 GRK WARRIOR: SNIPER V2")

# Sidebar for Login & Settings
with st.sidebar:
    st.header("🔐 Authentication")
    totp = st.text_input("Enter Fresh TOTP", type="password")
    idx_choice = st.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx_choice == "NIFTY" else "26009"
    
    if st.button("🚀 Login to Shoonya"):
        res = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, 
                                          vendor_code=VC, api_secret=KEY, imei="abc1234")
        if res and res.get('stat') == 'Ok':
            st.success(f"Connected: {res.get('uname')}")
        else:
            st.error("Login Failed! Check TOTP.")

    st.divider()
    if st.button("▶️ START BOT"): st.session_state.running = True
    if st.button("🛑 STOP BOT"): st.session_state.running = False

# Main Dashboard Layout
m1, m2, m3 = st.columns(3)
pnl_container = st.empty()

# --- TRADING ENGINE ---
if st.session_state.running:
    st.info("📡 Scanner Active...")
    log_box = st.empty()
    start_oi = 0
    
    while st.session_state.running:
        data = fetch_data(token)
        if data:
            lp, pc, sma, toi, vol, s1, r1, pivot = data
            if start_oi == 0: start_oi = toi

            # Logic Checks
            c_trend, c_sent = (lp > sma), (lp > pc)
            p_trend, p_sent = (lp < sma), (lp < pc)
            c_oi = (toi >= start_oi)
            c_score = sum([c_trend, c_sent, c_oi, True]) # vol placeholder True
            p_score = sum([p_trend, p_sent, c_oi, True])
            
            safety = 0.0
            status = "SCANNING 📡"
            if c_score >= 3 and lp > sma:
                status, safety = "CALL BUY ✅", round((c_score/4)*100, 1)
            elif p_score >= 3 and lp < sma:
                status, safety = "PUT BUY 🔥", round((p_score/4)*100, 1)

            # Update Metrics
            m1.metric("LTP", lp)
            m2.metric("TGT Hits", st.session_state.target_count)
            m3.metric("SL Hits", st.session_state.sl_count)

            # Live Trade Display
            with log_box.container():
                st.write(f"### Current Signal: {status} ({safety}%)")
                st.write(f"**Levels:** S1: {s1} | R1: {r1} | Pivot: {pivot}")
                
                # Trade Execution Logic
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    st.session_state.locked_entry = lp
                    st.session_state.trade_type = status
                    st.toast(f"Entry Taken @ {lp}")

                if st.session_state.locked_entry > 0:
                    is_call = "CALL" in st.session_state.trade_type
                    pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                    st.warning(f"🚀 ACTIVE TRADE: {st.session_state.trade_type} | Entry: {st.session_state.locked_entry} | PnL: {pnl}")
                    
                    # Exit Check
                    if pnl >= 40 or pnl <= -20:
                        res_text = "TARGET ✅" if pnl >= 40 else "STOPLOSS 🛑"
                        if pnl >= 40: st.session_state.target_count += 1
                        else: st.session_state.sl_count += 1
                        
                        hist_entry = f"{time.strftime('%H:%M:%S')} | {st.session_state.trade_type} | PnL: {pnl} | {res_text}"
                        st.session_state.trade_history.append(hist_entry)
                        st.session_state.locked_entry = 0
            
            # History Table
            if st.session_state.trade_history:
                st.write("---")
                st.write("📜 **Recent Trades**")
                st.table(st.session_state.trade_history[-5:])

        time.sleep(3)
        if not st.session_state.running: break
