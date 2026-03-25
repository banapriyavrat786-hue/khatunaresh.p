import streamlit as st
import pandas as pd
import time
from datetime import datetime
from api_helper import ShoonyaApiPy

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# Session State Initialization
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
        search_inst = "Nifty 50" if index_name == "NIFTY" else "Nifty Bank"
        chain = api.get_option_chain(exchange="NFO", instrument=search_inst, expiry="LATEST")
        
        if chain and 'values' in chain:
            df_oc = pd.DataFrame(chain['values'])
            res_strike = float(df_oc.loc[df_oc['ce_oi'].idxmax()]['stk'])
            sup_strike = float(df_oc.loc[df_oc['pe_oi'].idxmax()]['stk'])
            return sup_strike, res_strike, True
        return None, None, False
    except:
        return None, None, False

def fetch_data(token, index_name):
    # Data flags checklist ke liye
    checks = {"LTP": False, "History": False, "OI_Chain": False}
    try:
        q = api.get_quotes(exchange="NSE", token=token)
        if q and 'lp' in q:
            lp, pc = float(q['lp']), float(q.get('c', q['lp']))
            toi, vol = int(q.get('toi', 0)), int(q.get('v', 0))
            high, low = float(q.get('h', lp)), float(q.get('l', lp))
            checks["LTP"] = True
        else:
            return None, checks

        s1_oi, r1_oi, oi_status = get_oi_levels(index_name)
        checks["OI_Chain"] = oi_status
        
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if hist and isinstance(hist, list) and len(hist) > 10:
            checks["History"] = True
            df = pd.DataFrame(hist)
            df['intc'] = df['intc'].astype(float)
            sma = round(df['intc'].tail(10).mean(), 2)
            pivot = round((high + low + pc) / 3, 2)
            
            if s1_oi is None: s1_oi = round(pivot - (0.382 * (high - low)), 2)
            if r1_oi is None: r1_oi = round(pivot + (0.382 * (high - low)), 2)
            
            price_up = lp > df['intc'].iloc[-2]
            return (lp, pc, sma, toi, vol, s1_oi, r1_oi, pivot, price_up), checks
        return None, checks
    except: return None, checks

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
        data_bundle, data_checks = fetch_data(token, idx_choice)
        
        with placeholder.container():
            # --- DATA CHECKLIST SECTION ---
            st.subheader("🛠️ System Health & Data Checklist")
            c1, c2, c3 = st.columns(3)
            def get_icon(status): return "✅ Active" if status else "❌ Error/No Data"
            c1.markdown(f"**Live LTP:** {get_icon(data_checks['LTP'])}")
            c2.markdown(f"**Historical (SMA):** {get_icon(data_checks['History'])}")
            c3.markdown(f"**Option Chain (OI):** {get_icon(data_checks['OI_Chain'])}")
            st.divider()

            if data_bundle:
                lp, pc, sma, toi, vol, s1, r1, pivot, price_up = data_bundle
                if start_oi == 0: start_oi = toi
                
                # Logic
                c_mom = (price_up and toi > start_oi) 
                p_mom = (not price_up and toi > start_oi)
                c_score = sum([(lp > sma), (lp > pc), c_mom, (vol > 0)])
                p_score = sum([(lp < sma), (lp < pc), p_mom, (vol > 0)])

                if c_score >= 3 and lp > sma:
                    status, safety = "CALL BUY ✅", round((c_score/4)*100, 1)
                elif p_score >= 3 and lp < sma:
                    status, safety = "PUT BUY 🔥", round((p_score/4)*100, 1)
                else:
                    status, safety = "SCANNING 📡", 0.0

                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("LTP", lp, delta=round(lp-pc, 2))
                m2.metric("SMA (10)", sma)
                m3.metric("SAFETY", f"{safety}%")
                m4.metric("OI MOMENTUM", "BULLISH 📈" if c_mom else "BEARISH 📉" if p_mom else "NEUTRAL ⚖️")

                st.info(f"🎯 LEVELS | Support: {s1} | Resistance: {r1} | Pivot: {pivot}")
                st.subheader(f"SIGNAL: {status}")

                # Trade Management
                if safety >= 75.0 and st.session_state.locked_entry == 0:
                    st.session_state.locked_entry, st.session_state.entry_safety, st.session_state.trade_type = lp, safety, status

                if st.session_state.locked_entry > 0:
                    entry = st.session_state.locked_entry
                    pnl = round(lp - entry if "CALL" in st.session_state.trade_type else entry - lp, 2)
                    st.success(f"🚀 ACTIVE TRADE (@{st.session_state.entry_safety}%) | ENTRY: {entry}")
                    st.warning(f"💰 LIVE P&L: {pnl} Points")

                    if pnl >= 40 or pnl <= -20:
                        st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Type": st.session_state.trade_type, "Entry": entry, "Exit": lp, "P&L": pnl, "Safety": f"{st.session_state.entry_safety}%"})
                        st.session_state.locked_entry = 0

                if st.session_state.trade_history:
                    st.subheader("📜 Historical Trades")
                    st.table(pd.DataFrame(st.session_state.trade_history).tail(10))
            else:
                st.error("Waiting for Data... Please check the checklist above.")

        time.sleep(2)
