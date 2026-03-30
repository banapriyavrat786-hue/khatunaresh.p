import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"        # Angel client ID
API_KEY = "MT72qa1q"                 # SmartAPI key
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"  # TOTP secret

st.set_page_config(page_title="GRK Sniper Pro", layout="wide")
st.title("🚀 Option Chain Sniper Bot")
st.sidebar.title("Controls")

# -- SESSION STATE INIT --
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'obj' not in st.session_state:
    st.session_state.obj = None
if 'token_df' not in st.session_state:
    st.session_state.token_df = None

# -- HELPER FUNCTIONS --
def get_internet_time():
    """Get current Unix time (for OTP) from world clock."""
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return r.json()['unixtime']
    except:
        return int(time.time())

@st.cache_data(ttl=3600)
def load_tokens():
    """Download and cache the Angel scrip master JSON as a DataFrame."""
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        df = pd.DataFrame(res.json())
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        return df
    except Exception as e:
        st.error(f"Failed to load token master: {e}")
        return None

def attempt_reconnect():
    """Attempt to auto-relogin if session expired."""
    try:
        otp = pyotp.TOTP(TOTP_SECRET).at(get_internet_time())
        data = st.session_state.obj.generateSession(FIXED_CLIENT_ID, st.session_state.mpin, otp)
        return data.get('status', False)
    except:
        return False

# -- SIDEBAR INPUTS --
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (DDMMMYYYY)", "02APR2026")
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    if len(mpin) != 4:
        st.sidebar.error("Enter a 4-digit MPIN")
    else:
        st.session_state.mpin = mpin
        otp = pyotp.TOTP(TOTP_SECRET).at(get_internet_time())
        st.sidebar.info(f"OTP: {otp}")
        smart_obj = SmartConnect(api_key=API_KEY)
        try:
            login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        except Exception as e:
            st.sidebar.error(f"Login error: {e}")
            login = None
        if login and login.get('status'):
            st.sidebar.success("Connected ✔️")
            st.session_state.connected = True
            st.session_state.obj = smart_obj
            df = load_tokens()
            if df is not None:
                st.session_state.token_df = df
                st.sidebar.success("Tokens loaded")
            else:
                st.sidebar.error("Token load failed")
        else:
            msg = login.get('message') if login else "No response"
            st.sidebar.error(f"Login failed: {msg}")

# -- MAIN AREA --
col1, col2, col3 = st.columns(3)
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df

    try:
        # Fetch index spot LTP
        symbol = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        token = "26000" if index=="NIFTY" else "26009"
        res = obj.ltpData("NSE", symbol, token)
        if not res.get('status'):
            st.error("Session expired. Reconnecting...")
            st.session_state.connected = False
            if attempt_reconnect():
                st.experimental_rerun()
            else:
                st.stop()
        spot = res['data']['ltp']
        atm = round(spot/50)*50

        col1.metric("Spot", f"₹{spot}")
        col2.metric("ATM Strike", atm)
        col3.metric("Status", "LIVE ✅")
        st.markdown("### 📊 ATM Option Data")

        # Parse expiry
        expiry_dt = datetime.strptime(expiry_str, "%d%b%Y").date()

        # Filter instrument rows
        name = "NIFTY" if index=="NIFTY" else "BANKNIFTY"
        strikes = [atm, atm-50, atm+50, atm-100, atm+100]
        ce = pe = None
        for st_try in strikes:
            ce = df[(df.name==name) & (df.expiry==expiry_dt) &
                    (df.strike==(st_try*100.0)) & (df.symbol.str.endswith("CE"))]
            pe = df[(df.name==name) & (df.expiry==expiry_dt) &
                    (df.strike==(st_try*100.0)) & (df.symbol.str.endswith("PE"))]
            if not ce.empty and not pe.empty:
                atm = st_try
                break
        if ce is None or ce.empty or pe is None or pe.empty:
            st.error("Option data not found. Check expiry or strike.")
            if st.sidebar.checkbox("🔍 Debug: show token rows", False):
                st.write(df[df.name==name].head(10))
            st.stop()

        ce_row = ce.iloc[0]; pe_row = pe.iloc[0]
        # Fetch LTP and OI for CE/PE
        ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_row['token'])
        pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_row['token'])
        ce_ltp = ce_res['data']['ltp'] if ce_res.get('status') else 0
        pe_ltp = pe_res['data']['ltp'] if pe_res.get('status') else 0
        ce_oi = ce_res['data'].get('openInterest',0) if ce_res.get('status') else 0
        pe_oi = pe_res['data'].get('openInterest',0) if pe_res.get('status') else 0

        colA, colB = st.columns(2)
        colA.metric("Call LTP (CE)", f"₹{ce_ltp}")
        colB.metric("Put LTP (PE)", f"₹{pe_ltp}")

        # Compute PCR and signal
        total_oi = ce_oi + pe_oi + 1
        pcr = round(pe_oi/total_oi, 2)
        strength = int(pe_oi/total_oi * 100)
        support = atm if pe_oi>ce_oi else atm-50
        resistance = atm if ce_oi>pe_oi else atm+50
        if pcr>1:
            signal = "📈 BUY CALL"
        elif pcr<0.7:
            signal = "📉 BUY PUT"
        else:
            signal = "⚖️ WAIT"

        st.markdown("### 📊 Analysis")
        st.write(f"PCR = {pcr}")
        st.write(f"Strength = {strength}%")
        st.write(f"Support = {support}, Resistance = {resistance}")
        st.markdown(f"## **Signal: {signal}**")

    except Exception as e:
        st.error(f"Error: {e}")
    time.sleep(1)
    st.experimental_rerun()

else:
    col1.metric("Spot", "₹0")
    col2.metric("ATM Strike", "0")
    col3.metric("Status", "OFFLINE ❌")
