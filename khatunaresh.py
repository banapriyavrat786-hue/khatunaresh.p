import streamlit as st
import pandas as pd
import time
from datetime import datetime
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# Session States
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'api_instance' not in st.session_state:
    st.session_state.api_instance = ShoonyaApiPy()
    st.session_state.logged_in = False

api = st.session_state.api_instance

def get_oi_support_resistance(index):
    try:
        # Option Chain fetch karna (Highest OI strikes dhoondhne ke liye)
        inst = "NIFTY" if index == "NIFTY" else "BANKNIFTY"
        chain = api.get_option_chain(exchange="NFO", instrument=inst, expiry="LATEST") # Logic to get strikes
        if chain and 'values' in chain:
            df_oc = pd.DataFrame(chain['values'])
            # Sabse zyada OI wali strikes dhoondhna
            res_strike = df_oc.loc[df_oc['ce_oi'].idxmax()]['stk'] # Resistance (Highest CE OI)
            sup_strike = df_oc.loc[df_oc['pe_oi'].idxmax()]['stk'] # Support (Highest PE OI)
            return float(sup_strike), float(res_strike)
    except:
        return None, None

def fetch_data(token, index_name):
    try:
        q = api.get_quotes(exchange="NSE", token=token)
        if not q or 'lp' not in q: return None
        lp, pc = float(q['lp']), float(q.get('c', q['lp']))
        toi, vol = int(q.get('toi', 0)), int(q.get('v', 0))
        
        # --- Naya OI based Support/Resistance ---
        s1_oi, r1_oi = get_oi_support_resistance(index_name)
        
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if hist and isinstance(hist, list) and len(hist) > 10:
            df = pd.DataFrame(hist)
            df['intc'] = df['intc'].astype(float)
            sma = round(df['intc'].tail(10).mean(), 2)
            
            # Momentum logic: Price Change vs Vol Change
            price_mom = lp > df['intc'].iloc[-2]
            return lp, pc, sma, toi, vol, s1_oi, r1_oi, price_mom
        return None
    except: return None

# --- UI SETTINGS ---
st.set_page_config(page_title="GRK WARRIOR V3 PRO", layout="wide")
st.title("🚀 MKPV ULTRA SNIPER V3 | OI-MOMENTUM PRO")

with st.sidebar:
    idx_choice = st.radio("Select Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx_choice == "NIFTY" else "26009"
    totp = st.text_input("Enter TOTP", type="password")
    if st.button("Login"):
        res = api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if res: st.session_state.logged_in = True

if st.session_state.logged_in:
    placeholder = st.empty()
    start_oi = 0

    while True:
        data = fetch_data(token, idx_choice)
        if data:
            lp, pc, sma, toi, vol, s1, r1, price_mom = data
            if start_oi == 0: start_oi = toi
            
            # --- ADVANCED LOGIC (Price + OI + Vol Momentum) ---
            c_trend, c_sent = (lp > sma), (lp > pc)
            c_mom = (price_mom and toi > start_oi) # Price up + OI up = Long Build-up
            
            p_trend, p_sent = (lp < sma), (lp < pc)
            p_mom = (not price_mom and toi > start_oi) # Price down + OI up = Short Build-up

            c_score = sum([c_trend, c_sent, c_mom, (vol > 0)])
            p_score = sum([p_trend, p_sent, p_mom, (vol > 0)])

            # Signal with 75% Safety (3/4 conditions)
            if c_score >= 3 and lp > sma:
                status, safety = "CALL BUY ✅", round((c_score/4)*100, 1)
            elif p_score >= 3 and lp < sma:
                status, safety = "PUT BUY 🔥", round((p_score/4)*100, 1)
            else:
                status, safety = "SCANNING 📡", 0.0

            with placeholder.container():
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("LTP", lp, delta=round(lp-pc, 2))
                m2.metric("SMA (10)", sma)
                m3.metric("SAFETY", f"{safety}%")
                m4.metric("OI MOMENTUM", "BULLISH 📈" if c_mom else "BEARISH 📉" if p_mom else "NEUTRAL ⚖️")

                st.divider()
                # Naya Support Resistance Display
                st.warning(f"🏦 OI DATA LEVELS | Major Support: {s1 if s1 else 'Calculating...'} | Major Resistance: {r1 if r1 else 'Calculating...'}")
                
                st.subheader(f"SIGNAL: {status}")

                # Trade Management
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    # Additional check: Price should be away from Resistance for Call, away from Support for Put
                    if (status == "CALL BUY ✅" and lp < r1 - 10) or (status == "PUT BUY 🔥" and lp > s1 + 10):
                        st.session_state.locked_entry = lp
                        st.session_state.trade_type = status
                        st.session_state.entry_safety = safety

                if st.session_state.locked_entry > 0:
                    entry = st.session_state.locked_entry
                    pnl = round(lp - entry if "CALL" in st.session_state.trade_type else entry - lp, 2)
                    st.success(f"🚀 ACTIVE TRADE (@{st.session_state.entry_safety}%) | ENTRY: {entry}")
                    st.warning(f"💰 LIVE P&L: {pnl} Points")

                    if pnl >= 40 or pnl <= -20:
                        st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Type": st.session_state.trade_type, "Entry": entry, "Exit": lp, "P&L": pnl, "Safety": f"{st.session_state.entry_safety}%"})
                        st.session_state.locked_entry = 0

                if st.session_state.trade_history:
                    st.table(pd.DataFrame(st.session_state.trade_history).tail(5))

        time.sleep(2)
