import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"        # Your Angel client ID
API_KEY = "MT72qa1q"                 # Your SmartAPI key
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"  # Your Angel TOTP secret

st.set_page_config(page_title="GRK SNIPER PRO MAX", layout="wide")
st.title("🚀 MKPV SNIPER PRO MAX")
st.sidebar.title("🔧 Controls")

# -- SESSION STATE INITIALIZATION --
if 'obj' not in st.session_state:
    st.session_state.obj = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'token_df' not in st.session_state:
    st.session_state.token_df = None

# -- Helper Functions --
def get_internet_time():
    """Get current unix time from Internet for OTP accuracy."""
    try:
        res = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return res.json()['unixtime']
    except:
        return int(time.time())

@st.cache_data(ttl=3600)
def load_tokens():
    """Fetch and cache the Angel scrip master JSON into a DataFrame."""
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        df = pd.DataFrame(res.json())
        # Parse expiry to datetime.date for robust matching
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        return df
    except Exception as e:
        st.error(f"❌ Failed to load instrument master: {e}")
        return None

def attempt_reconnect():
    """Try to auto-relogin on session expiry."""
    try:
        otp = pyotp.TOTP(TOTP_SECRET).at(get_internet_time())
        data = st.session_state.obj.generateSession(FIXED_CLIENT_ID, st.session_state.mpin, otp)
        if data['status']:
            st.sidebar.success("✅ Reconnected automatically")
            return True
        else:
            return False
    except Exception:
        return False

# -- Sidebar: Input --
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_input = st.sidebar.text_input("Expiry (DDMMMYYYY)", "02APR2026")
mpin_input = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Sync & Connect"):
    if len(mpin_input) != 4 or not mpin_input.isdigit():
        st.sidebar.error("Enter a valid 4-digit MPIN")
    else:
        # Save MPIN for reconnects
        st.session_state.mpin = mpin_input
        # Generate OTP using internet time
        current_time = get_internet_time()
        otp = pyotp.TOTP(TOTP_SECRET).at(current_time)
        st.sidebar.info(f"Generated OTP: {otp}")
        # Attempt login
        obj = SmartConnect(api_key=API_KEY)
        try:
            login_data = obj.generateSession(FIXED_CLIENT_ID, mpin_input, otp)
        except Exception as e:
            st.sidebar.error(f"Login error: {e}")
            login_data = None
        if login_data and login_data.get('status'):
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Connected!")
            # Load tokens
            token_df = load_tokens()
            if token_df is not None:
                st.session_state.token_df = token_df
                st.sidebar.success("✅ Token master loaded")
            else:
                st.sidebar.error("Failed to load instrument master")
        else:
            msg = login_data.get('message', 'Unknown error') if login_data else 'No response'
            st.sidebar.error(f"❌ Login failed: {msg}")

# -- Main Interface --
col1, col2, col3 = st.columns(3)
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df

    try:
        # -- Fetch Spot LTP --
        symbol = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        token = "26000" if index=="NIFTY" else "26009"
        ltp_resp = obj.ltpData("NSE", symbol, token)

        if not ltp_resp.get('status'):
            st.error("Session expired. Reconnecting...")
            st.session_state.connected = False
            if attempt_reconnect():
                st.experimental_rerun()
            else:
                st.stop()

        spot_price = ltp_resp['data']['ltp']
        atm = round(spot_price / 50) * 50

        col1.metric("SPOT", f"₹{spot_price}")
        col2.metric("ATM", atm)
        col3.metric("STATUS", "LIVE ✅")

        st.markdown("### 📊 ATM Option Chain")
        # -- Parse expiry date input --
        expiry_dt = datetime.strptime(expiry_input, "%d%b%Y").date()

        # -- Prepare match filters --
        df_name = "NIFTY" if index=="NIFTY" else "BANKNIFTY"
        # List of strikes to try (in ₹)
        strikes_to_try = [atm, atm-50, atm+50, atm-100, atm+100]
        ce_row = pe_row = pd.DataFrame()

        # -- Find CE and PE tokens with fallback strikes --
        for strike in strikes_to_try:
            ce_row = df[(df['name']==df_name) & (df['expiry']==expiry_dt) &
                        (df['strike']==float(strike*100)) & df['symbol'].str.endswith("CE")]
            pe_row = df[(df['name']==df_name) & (df['expiry']==expiry_dt) &
                        (df['strike']==float(strike*100)) & df['symbol'].str.endswith("PE")]
            if not ce_row.empty and not pe_row.empty:
                atm = strike
                break

        if ce_row.empty or pe_row.empty:
            st.error("❌ Option not found. Check expiry/strike format.")
            # Debug view
            if st.sidebar.checkbox("🔍 Debug: Show NIFTY Instruments", False):
                st.write(df[df['name']==df_name].head(10))
            st.stop()

        ce_data = ce_row.iloc[0]
        pe_data = pe_row.iloc[0]

        # -- Fetch CE/PE LTP and OI --
        ce_resp = obj.ltpData("NFO", ce_data['symbol'], ce_data['token'])
        pe_resp = obj.ltpData("NFO", pe_data['symbol'], pe_data['token'])

        ce_ltp = ce_resp['data']['ltp'] if ce_resp.get('status') else 0
        pe_ltp = pe_resp['data']['ltp'] if pe_resp.get('status') else 0
        ce_oi = ce_resp['data'].get('openInterest', 0) if ce_resp.get('status') else 0
        pe_oi = pe_resp['data'].get('openInterest', 0) if pe_resp.get('status') else 0

        colA, colB = st.columns(2)
        colA.metric("CALL LTP", f"₹{ce_ltp}")
        colB.metric("PUT LTP", f"₹{pe_ltp}")

        # -- Analysis Metrics --
        total_oi = ce_oi + pe_oi + 1  # +1 to avoid div by zero
        pcr = round(pe_oi / total_oi, 2)
        strength = int(pe_oi / total_oi * 100)
        # Support/Resistance logic
        support = atm if pe_oi > ce_oi else atm - 50
        resistance = atm if ce_oi > pe_oi else atm + 50
        # Signal logic
        if pcr > 1:
            signal = "📈 BUY CALL"
        elif pcr < 0.7:
            signal = "📉 BUY PUT"
        else:
            signal = "⚖️ WAIT"

        st.markdown("### 📊 Analysis")
        st.write(f"**PCR:** {pcr}  (Put OI / Call OI)")
        st.write(f"**Strength:** {strength}%")
        st.write(f"**Support:** {support}")
        st.write(f"**Resistance:** {resistance}")
        st.markdown(f"## ⚡ SIGNAL: {signal}")

    except Exception as e:
        st.error(f"Unexpected error: {e}")
        st.stop()

    # Auto-refresh for live updates
    time.sleep(1)
    st.experimental_rerun()

else:
    col1.metric("SPOT", "₹0")
    col2.metric("ATM", "0")
    col3.metric("STATUS", "OFFLINE ❌")
