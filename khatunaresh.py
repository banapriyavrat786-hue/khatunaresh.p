import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# ---------- CONFIG ----------
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="Option Chain Sniper", layout="wide")
st.title("🚀 Option-Chain Sniper Bot")

# ---------- SESSION STATE ----------
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'obj' not in st.session_state:
    st.session_state.obj = None
if 'token_df' not in st.session_state:
    st.session_state.token_df = None

# ---------- HELPERS ----------
def get_internet_time():
    try:
        return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except:
        return int(time.time())

@st.cache_data(ttl=3600)
def load_scrip_master():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    df = pd.DataFrame(res.json())
    df['expiry'] = pd.to_datetime(df['expiry'], errors='coerce').dt.date
    return df

def attempt_reconnect():
    try:
        otp = pyotp.TOTP(TOTP_SECRET).at(get_internet_time())
        data = st.session_state.obj.generateSession(FIXED_CLIENT_ID, st.session_state.mpin, otp)
        return data.get('status', False)
    except:
        return False

# ---------- SIDEBAR ----------
st.sidebar.title("🔧 Configuration")
mpin = st.sidebar.text_input("4-digit MPIN", type="password", max_chars=4)
if st.sidebar.button("🔑 Connect Bot"):
    if len(mpin) != 4:
        st.sidebar.error("Enter a valid 4-digit MPIN")
    else:
        st.session_state.mpin = mpin
        otp = pyotp.TOTP(TOTP_SECRET).at(get_internet_time())
        st.sidebar.info(f"OTP: {otp}")
        smart_api = SmartConnect(API_KEY)
        try:
            login_data = smart_api.generateSession(FIXED_CLIENT_ID, mpin, otp)
        except Exception as e:
            st.sidebar.error(f"Login error: {e}")
            login_data = None
        if login_data and login_data.get('status'):
            st.sidebar.success("✅ Connected")
            st.session_state.obj = smart_api
            st.session_state.connected = True
            df = load_scrip_master()
            st.session_state.token_df = df
            st.sidebar.success("Tokens Loaded")
        else:
            msg = login_data.get('message') if login_data else 'Failed to login'
            st.sidebar.error(msg)

# ---------- MAIN ----------
col1, col2, col3 = st.columns(3)
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df

    try:
        # --- Fetch Spot Price ---
        spot_res = obj.ltpData("NSE", "Nifty 50", "26000")
        if not spot_res.get('status'):
            st.error("Session expired. Attempting reconnect...")
            if attempt_reconnect():
                st.experimental_rerun()
            else:
                st.stop()
        spot = spot_res['data']['ltp']
        atm = round(spot/50)*50

        col1.metric("Spot (NIFTY)", f"₹{spot}")
        col2.metric("ATM Strike", atm)
        col3.metric("Status", "🟢 Live")

        st.markdown("### 🔍 Instruments Data")

        # --- Parse and Filter Instruments ---
        expiry_input = st.sidebar.text_input("Expiry (DDMMMYYYY)", "02APR2026")
        expiry_dt = datetime.strptime(expiry_input, "%d%b%Y").date()
        st.write(f"Selected Expiry: {expiry_dt}")
        available = sorted(df['expiry'].dropna().unique())
        st.write(f"Available Expiries: {available[:5]}")

        if expiry_dt not in df['expiry'].values:
            st.warning("Expiry not found, using nearest available.")
            expiry_dt = available[0]

        df_sel = df[(df['expiry'] == expiry_dt) & (df['name']=="NIFTY")]

        # --- Nearest Strike Fallback ---
        df_sel['strike_rupees'] = df_sel['strike'].astype(float)/100
        nearest = df_sel.iloc[(df_sel['strike_rupees'] - atm).abs().argsort()[:1]]
        atm = int(nearest['strike_rupees'].iloc[0])

        st.write(f"Using Strike: ₹{atm}")
        ce_row = df_sel[(df_sel['strike_rupees']==atm) & df_sel['symbol'].str.endswith("CE")]
        pe_row = df_sel[(df_sel['strike_rupees']==atm) & df_sel['symbol'].str.endswith("PE")]

        if ce_row.empty or pe_row.empty:
            st.error("⚠️ CE/PE not found for strike")
            st.stop()

        ce = ce_row.iloc[0]
        pe = pe_row.iloc[0]

        # --- Fetch Option Prices ---
        ce_data = obj.ltpData("NFO", ce['symbol'], ce['token'])
        pe_data = obj.ltpData("NFO", pe['symbol'], pe['token'])
        ce_ltp = ce_data['data']['ltp'] if ce_data.get('status') else 0
        pe_ltp = pe_data['data']['ltp'] if pe_data.get('status') else 0

        colA, colB = st.columns(2)
        colA.metric("CALL CE LTP", f"₹{ce_ltp}")
        colB.metric("PUT PE LTP", f"₹{pe_ltp}")

        # --- Compute Metrics ---
        st.markdown("### 📊 Analysis")
        total_oi = ce_ltp + pe_ltp + 1
        pcr = round(pe_ltp/total_oi, 2)
        strength = int(pe_ltp/total_oi*100)
        support = atm if pe_ltp > ce_ltp else atm-50
        resistance = atm if ce_ltp > pe_ltp else atm+50
        signal = "📈 BUY CALL" if pcr>1 else ("📉 BUY PUT" if pcr<0.7 else "⚖️ WAIT")
        st.write(f"PCR = {pcr}")
        st.write(f"Strength = {strength}%")
        st.write(f"Support = {support}")
        st.write(f"Resistance = {resistance}")
        st.markdown(f"## **Signal: {signal}**")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    col1.metric("Spot (NIFTY)", "₹0")
    col2.metric("ATM Strike", 0)
    col3.metric("Status", "🔴 Disconnected")
