import streamlit as st
import pandas as pd
import time
from datetime import datetime
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# Session State Initialization (Crash se bachne ke liye)
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_safety' not in st.session_state: st.session_state.entry_safety = 0
if 'trade_type' not in st.session_state: st.session_state.trade_type = ""
if 'api_instance' not in st.session_state:
    st.session_state.api_instance = ShoonyaApiPy()
    st.session_state.logged_in = False

api = st.session_state.api_instance

# --- FUNCTIONS ---

def get_oi_levels(index_name):
    """Highest OI strikes dhoondhne ke liye function"""
    try:
        # Shoonya API ke liye sahi instrument name
        search_inst = "Nifty 50" if index_name == "NIFTY" else "Nifty Bank"
        chain = api.get_option_chain(exchange="NFO", instrument=search_inst, expiry="LATEST")
        
        if chain and 'values' in chain:
            df_oc = pd.DataFrame(chain['values'])
            # Highest Call OI = Resistance | Highest Put OI = Support
            res_strike = float(df_oc.loc[df_oc['ce_oi'].idxmax()]['stk'])
            sup_strike = float(df_oc.loc[df_oc['pe_oi'].idxmax()]['stk'])
            return sup_strike, res_strike
        return None, None
    except:
        return None, None

def fetch_data(token, index_name):
    try:
        q = api.get_quotes(exchange="NSE", token=token)
        if not q or 'lp' not in q: return None
        
        lp, pc = float(q['lp']), float(q.get('c', q['lp']))
        toi, vol = int(q.get('toi', 0)), int(q.get('v', 0))
        high, low = float(q.get('h', lp)), float(q.get('l', lp))
        
        # OI Data fetch karna
        s1_oi, r1_oi = get_oi_levels(index_name)
        
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if hist and isinstance(hist, list) and len(hist) > 10:
            df = pd.DataFrame(hist)
            df['intc'] = df['intc'].astype(float)
            sma = round(df['intc'].tail(10).mean(), 2)
            pivot = round((high + low + pc) / 3, 2)
            
            # --- BACKUP LOGIC: Agar OI data na mile toh Pivot use karein ---
            if s1_oi is None: s1_oi = round(pivot - (0.382 * (high - low)), 2)
            if r1_oi is None: r1_oi = round(pivot + (0.382 * (high - low)), 2)
            
            # Momentum: Current Price vs Previous Candle Price
            price_up = lp > df['intc'].iloc[-2]
            return lp, pc, sma, toi, vol, s1_oi, r1_oi, pivot, price_up
        return None
    except: return None

# --- UI LAYOUT ---
st.set_page_config(page_title="GRK WARRIOR V3 PRO", layout="wide")
st.title("🚀 MKPV ULTRA SNIPER V3 | OI-MOMENTUM PRO")

with st.sidebar:
    idx_choice = st.radio("Select Index", ["NIFTY", "BANKNIFTY"])
    token = "26000" if idx_choice == "NIFTY" else "26009"
    totp = st.text_input("Enter Fresh TOTP", type="password")
    if st.button("Login"):
        res = api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if res and res.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.success("Logged In!")

if st.session_state.logged_in:
    placeholder = st.empty()
    start_oi = 0

    while True:
        data = fetch_data(token, idx_choice)
        if data:
            lp, pc, sma, toi, vol, s1, r1, pivot, price_up = data
            if start_oi == 0: start_oi = toi
            
            # --- ADVANCED LOGIC (Price + OI Momentum) ---
            c_trend, c_sent = (lp > sma), (lp > pc)
            c_mom = (price_up and toi > start_oi) 
            
            p_trend, p_sent = (lp < sma), (lp < pc)
            p_mom = (not price_up and toi > start_oi)

            c_score = sum([c_trend, c_sent, c_mom, (vol > 0)])
            p_score = sum([p_trend, p_sent, p_mom, (vol > 0)])

            if c_score >= 3 and lp > sma:
                status, safety = "CALL BUY ✅", round((c_score/4)*100, 1)
            elif p_score >= 3 and lp < sma:
                status, safety = "PUT BUY 🔥", round((p_score/4)*100, 1)
            else:
                status, safety = "SCANNING 📡", 0.0

            with placeholder.container():
                # Dashboard Metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("LTP", lp, delta=round(lp-pc, 2))
                col2.metric("SMA (10)", sma)
                col3.metric("SAFETY", f"{safety}%")
                col4.metric("OI MOMENTUM", "BULLISH 📈" if c_mom else "BEARISH 📉" if p_mom else "NEUTRAL ⚖️")

                st.divider()
                # Levels Display
                st.info(f"🎯 LEVELS | Support: {s1} | Resistance: {r1} | Pivot: {pivot}")
                st.subheader(f"SIGNAL: {status}")

                # --- TRADE EXECUTION ---
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    st.session_state.locked_entry = lp
                    st.session_state.entry_safety = safety
                    st.session_state.trade_type = status

                # --- ACTIVE TRADE DISPLAY ---
                if st.session_state.locked_entry > 0:
                    entry = st.session_state.locked_entry
                    e_safety = st.session_state.get('entry_safety', 0)
                    pnl = round(lp - entry if "CALL" in st.session_state.trade_type else entry - lp, 2)
                    
                    st.success(f"🚀 ACTIVE TRADE (@{e_safety}%) | ENTRY: {entry}")
                    st.warning(f"💰 LIVE P&L: {pnl} Points")

                    # Exit Logic
                    if pnl >= 40 or pnl <= -20:
                        st.session_state.trade_history.append({
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Type": st.session_state.trade_type,
                            "Entry": entry, "Exit": lp, "P&L": pnl, "Safety": f"{e_safety}%"
                        })
                        st.session_state.locked_entry = 0
                        st.session_state.entry_safety = 0

                # History Table
                if st.session_state.trade_history:
                    st.divider()
                    st.subheader("📜 Historical Trades")
                    st.table(pd.DataFrame(st.session_state.trade_history).tail(10))

        time.sleep(2)
