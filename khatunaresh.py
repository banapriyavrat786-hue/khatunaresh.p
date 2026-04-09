import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V59", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Strict Risk-Reward Engine")

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history', 'vol_history', 'last_valid_data']:
    if key not in st.session_state:
        if key == 'price_history': st.session_state[key] = []
        elif key == 'vol_history': st.session_state[key] = []
        elif key == 'trade_history': st.session_state[key] = []
        elif key == 'last_valid_data': st.session_state[key] = {'ce_oi': 0, 'pe_oi': 0, 'ce_vol': 0, 'pe_vol': 0, 'total_ce_oi': 0, 'total_pe_oi': 0}
        else: st.session_state[key] = None

def get_time():
    try:
        return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except:
        return int(time.time())

@st.cache_data(ttl=3600, show_spinner="Downloading Tokens...")
def load_tokens():
    try:
        res = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=30)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            return df[df['exch_seg'] == "NFO"]
    except: pass
    return None

# -- SIDEBAR CONTROLS --
st.sidebar.title("⚙️ Robot Controls")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED (Auto-Refresh)", value=False)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)

st.sidebar.markdown("---")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 10, 1)

st.sidebar.subheader("🛡️ Strict Risk & Reward limits")
# 💡 V59 NEW: Strict Risk Reward Guards
min_target_pts = st.sidebar.number_input("Minimum Target (Pts)", value=20.0, step=5.0)
max_sl_pts = st.sidebar.number_input("Maximum StopLoss (Pts)", value=15.0, step=5.0)

st.sidebar.subheader("🎛️ AI Filters & Safety")
history_ticks = st.sidebar.number_input("VWAP Speed (Ticks)", min_value=10, max_value=200, value=30, step=10)
min_vix = st.sidebar.number_input("Minimum VIX Required", value=11.0, step=0.5)
trend_buffer = st.sidebar.number_input("VWAP Noise Buffer", value=2.0, step=0.5)

mpin = st.sidebar.text_input("MPIN", type="password")

# -- LOGIN --
if st.sidebar.button("🔑 Connect"):
    st.session_state.token_df = load_tokens()
    if st.session_state.token_df is not None:
        otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_time())
        obj = SmartConnect(api_key=API_KEY)
        login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        
        if login.get('status'):
            st.session_state.connected = True
            st.session_state.obj = obj
            st.sidebar.success("✅ Connected Successfully!")
        else: st.sidebar.error("❌ Login Failed.")
    else: st.sidebar.error("❌ Token Data Failed.")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    if live_feed:
        obj = st.session_state.obj
        df = st.session_state.token_df

        if df is None or df.empty: 
            st.error("Token List is empty.")
            st.stop()

        step = 50 if index == "NIFTY" else 100
        lot_size = 50 if index == "NIFTY" else 15
        qty = lot_size * lots

        name = "Nifty 50" if index == "NIFTY" else "Nifty Bank"
        token = "26000" if index == "NIFTY" else "26009"

        try:
            # 1. FETCH SPOT & VIX
            res = obj.ltpData("NSE", name, token)
            vix_res = obj.ltpData("NSE", "INDIA VIX", "26017") 
            
            if res and res.get('status'):
                spot = float(res['data']['ltp'])
                live_vix = float(vix_res['data']['ltp']) if (vix_res and vix_res.get('status')) else 12.0

                atm = int(round(spot / step) * step)
                search_prefix = f"{index}{expiry}"

                try:
                    ce_row = df[df['symbol'] == f"{search_prefix}{atm}CE"].iloc[0]
                    pe_row = df[df['symbol'] == f"{search_prefix}{atm}PE"].iloc[0]
                    ce_tok = str(ce_row['token']).split('.')[0]
                    pe_tok = str(pe_row['token']).split('.')[0]
                except:
                    ce_tok, pe_tok = "", ""

                # 2. LIVE DYNAMIC RANGE FINDER
                ce_oi = st.session_state.last_valid_data['ce_oi']
                pe_oi = st.session_state.last_valid_data['pe_oi']
                ce_vol = st.session_state.last_valid_data['ce_vol']
                pe_vol = st.session_state.last_valid_data['pe_vol']
                total_ce_oi = st.session_state.last_valid_data['total_ce_oi']
                total_pe_oi = st.session_state.last_valid_data['total_pe_oi']
                
                ce_ltp = pe_ltp = 0.0
                
                max_ce_power, resistance_strike = 0, atm + (step*2) 
                max_pe_power, support_strike = 0, atm - (step*2)

                if ce_tok and pe_tok:
                    strikes_to_scan = [atm + (step * i) for i in range(-6, 7)]
                    ce_tokens = []
                    pe_tokens = []
                    strike_map = {}

                    for s in strikes_to_scan:
                        c_df = df[df['symbol'] == f"{search_prefix}{s}CE"]
                        p_df = df[df['symbol'] == f"{search_prefix}{s}PE"]
                        if not c_df.empty and not p_df.empty:
                            c_tok_id = str(c_df.iloc[0]['token']).split('.')[0]
                            p_tok_id = str(p_df.iloc[0]['token']).split('.')[0]
                            ce_tokens.append(c_tok_id)
                            pe_tokens.append(p_tok_id)
                            strike_map[c_tok_id] = {'type': 'CE', 'strike': s}
                            strike_map[p_tok_id] = {'type': 'PE', 'strike': s}

                    try:
                        c_ltp_res = obj.ltpData("NFO", ce_row['symbol'], ce_tok)
                        p_ltp_res = obj.ltpData("NFO", pe_row['symbol'], pe_tok)
                        if c_ltp_res and c_ltp_res.get('status'): ce_ltp = float(c_ltp_res['data']['ltp'])
                        if p_ltp_res and p_ltp_res
