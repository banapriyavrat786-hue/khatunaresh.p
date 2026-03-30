import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests
import pandas as pd

# ==========================================
# CONFIG
# ==========================================
FIXED_CLIENT_ID = "P51646259"

st.set_page_config(page_title="GRK SNIPER FINAL", layout="wide")

# ==========================================
# SESSION STATE
# ==========================================
if 'connected' not in st.session_state:
    st.session_state.connected = False

if 'obj' not in st.session_state:
    st.session_state.obj = None

if 'token_df' not in st.session_state:
    st.session_state.token_df = None

# ==========================================
# TOKEN LOADER
# ==========================================
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            st.error("❌ Failed to fetch token file")
            return None
        
        data = response.json()
        df = pd.DataFrame(data)
        
        return df
    
    except Exception as e:
        st.error(f"❌ Token Load Error: {e}")
        return None

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🎯 GRK SNIPER FINAL")

idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])

expiry = st.sidebar.text_input("Expiry (DDMMMYYYY)", "02APR2026")

st.sidebar.markdown("---")

api_key_input = st.sidebar.text_input("SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("MPIN", type="password")
totp_secret = st.sidebar.text_input("TOTP Secret", type="password")

# ==========================================
# LOAD TOKEN + CONNECT
# ==========================================
if st.sidebar.button("Load Tokens & Connect"):

    # 🔹 Load Token DB
    df = load_tokens()
    
    if df is not None:
        st.session_state.token_df = df
        st.sidebar.success("✅ Tokens Loaded")
    else:
        st.sidebar.error("❌ Token load failed")
        st.stop()

    # 🔹 Login
    try:
        otp = pyotp.TOTP(totp_secret).now()

        obj = SmartConnect(api_key=api_key_input.strip())
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)

        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Connected!")
        else:
            st.sidebar.error("❌ Login Failed")

    except Exception as e:
        st.sidebar.error(f"❌ Login Error: {e}")

# ==========================================
# MAIN UI
# ==========================================
st.title("🚀 MKPV SNIPER | LIVE DATA & OI")
st.divider()

col1, col2, col3 = st.columns(3)

# ==========================================
# LIVE DATA
# ==========================================
if st.session_state.connected:

    try:
        # INDEX
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"

        ltp_data = st.session_state.obj.ltpData(
            exchange="NSE",
            tradingsymbol=t_sym,
            symboltoken=t_tok
        )

        if not ltp_data['status']:
            st.warning("Session expired. Reconnect.")
            st.session_state.connected = False
            st.stop()

        spot = ltp_data['data']['ltp']

        # ATM STRIKE
        atm = round(spot / 50) * 50

        col1.metric("SPOT PRICE", f"₹{spot}")
        col2.metric("ATM STRIKE", atm)
        col3.metric("STATUS", "STABLE ✅")

        st.markdown("### 📊 ATM Option Chain")

        # ==========================================
        # OPTION TOKEN SEARCH
        # ==========================================
        df = st.session_state.token_df

        search = f"NIFTY{expiry}{atm}"

        ce_row = df[df['symbol'].str.contains(search + "CE", na=False)]
        pe_row = df[df['symbol'].str.contains(search + "PE", na=False)]

        if ce_row.empty or pe_row.empty:
            st.warning("⚠️ Symbols not found. Check expiry format.")
            st.stop()

        ce_token = ce_row.iloc[0]['token']
        pe_token = pe_row.iloc[0]['token']

        ce_symbol = ce_row.iloc[0]['symbol']
        pe_symbol = pe_row.iloc[0]['symbol']

        # ==========================================
        # FETCH OPTION LTP
        # ==========================================
        ce_ltp = st.session_state.obj.ltpData("NFO", ce_symbol, ce_token)
        pe_ltp = st.session_state.obj.ltpData("NFO", pe_symbol, pe_token)

        colA, colB = st.columns(2)

        if ce_ltp['status']:
            colA.metric("CALL (CE)", f"₹{ce_ltp['data']['ltp']}")
        else:
            colA.metric("CALL (CE)", "Error")

        if pe_ltp['status']:
            colB.metric("PUT (PE)", f"₹{pe_ltp['data']['ltp']}")
        else:
            colB.metric("PUT (PE)", "Error")

    except Exception as e:
        st.error(f"❌ Error: {e}")

    time.sleep(1)
    st.rerun()

# ==========================================
# OFFLINE
# ==========================================
else:
    col1.metric("SPOT PRICE", "₹0")
    col2.metric("ATM STRIKE", "0")
    col3.metric("STATUS", "OFFLINE ❌")
