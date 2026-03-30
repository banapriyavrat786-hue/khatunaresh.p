import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import time
import pandas as pd

# ==========================================
# CONFIG
# ==========================================
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK SNIPER PRO MAX", layout="wide")

# ==========================================
# SESSION STATE
# ==========================================
if "connected" not in st.session_state:
    st.session_state.connected = False

if "obj" not in st.session_state:
    st.session_state.obj = None

if "df" not in st.session_state:
    st.session_state.df = None

# ==========================================
# TIME FIX
# ==========================================
def get_time():
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return r.json()['unixtime']
    except:
        return time.time()

# ==========================================
# LOAD TOKENS
# ==========================================
def load_tokens():
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        df = pd.DataFrame(r.json())
        df['expiry'] = pd.to_datetime(df['expiry'])
        return df
    except:
        return None

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🚀 GRK SNIPER PRO MAX")

index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (DDMMMYYYY)", "02APR2026")
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Sync & Connect"):

    if len(mpin) != 4:
        st.sidebar.error("Enter valid MPIN")
    else:
        try:
            t = get_time()
            otp = pyotp.TOTP(TOTP_SECRET).at(t)

            st.sidebar.info(f"OTP: {otp}")

            obj = SmartConnect(api_key=API_KEY)
            data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)

            if data['status']:
                st.session_state.obj = obj
                st.session_state.connected = True

                df = load_tokens()
                if df is not None:
                    st.session_state.df = df
                    st.sidebar.success("✅ Connected + Tokens Loaded")
                else:
                    st.sidebar.error("Token load failed")

            else:
                st.sidebar.error(data['message'])

        except Exception as e:
            st.sidebar.error(str(e))

# ==========================================
# MAIN
# ==========================================
st.title("🚀 MKPV SNIPER PRO MAX")
st.divider()

col1, col2, col3 = st.columns(3)

# ==========================================
# LIVE MODE
# ==========================================
if st.session_state.connected:

    obj = st.session_state.obj
    df = st.session_state.df

    try:
        # INDEX
        if index == "NIFTY":
            sym = "Nifty 50"
            tok = "26000"
            name = "NIFTY"
        else:
            sym = "Nifty Bank"
            tok = "26009"
            name = "BANKNIFTY"

        res = obj.ltpData("NSE", sym, tok)

        if not res['status']:
            st.error("Session expired")
            st.session_state.connected = False
            st.stop()

        spot = res['data']['ltp']
        atm = round(spot / 50) * 50

        col1.metric("SPOT", f"₹{spot}")
        col2.metric("ATM", atm)
        col3.metric("STATUS", "LIVE ✅")

        st.markdown("### 📊 ATM Option Chain")

        # ==========================================
        # SMART MATCH ENGINE (FINAL)
        # ==========================================
        expiry_dt = pd.to_datetime(expiry, format="%d%b%Y")

        strike_list = [atm, atm-50, atm+50, atm-100, atm+100]

        ce = None
        pe = None

        for strike_try in strike_list:

            ce_row = df[
                (df['name'] == name) &
                (df['expiry'] == expiry_dt) &
                (df['strike'] == float(strike_try * 100)) &
                (df['symbol'].str.endswith("CE"))
            ]

            pe_row = df[
                (df['name'] == name) &
                (df['expiry'] == expiry_dt) &
                (df['strike'] == float(strike_try * 100)) &
                (df['symbol'].str.endswith("PE"))
            ]

            if not ce_row.empty and not pe_row.empty:
                ce = ce_row.iloc[0]
                pe = pe_row.iloc[0]
                atm = strike_try
                break

        if ce is None or pe is None:
            st.error("❌ Option not found. Try correct expiry.")
            st.stop()

        # ==========================================
        # FETCH DATA
        # ==========================================
        ce_res = obj.ltpData("NFO", ce['symbol'], ce['token'])
        pe_res = obj.ltpData("NFO", pe['symbol'], pe['token'])

        ce_ltp = ce_res['data']['ltp'] if ce_res['status'] else 0
        pe_ltp = pe_res['data']['ltp'] if pe_res['status'] else 0

        ce_oi = ce_res['data'].get('openInterest', 0) if ce_res['status'] else 0
        pe_oi = pe_res['data'].get('openInterest', 0) if pe_res['status'] else 0

        # ==========================================
        # ANALYSIS
        # ==========================================
        total = ce_oi + pe_oi + 1

        pcr = round(pe_oi / total, 2)
        strength = int((pe_oi / total) * 100)

        support = atm if pe_oi > ce_oi else atm - 50
        resistance = atm if ce_oi > pe_oi else atm + 50

        if pcr > 1:
            signal = "📈 BUY CALL"
        elif pcr < 0.7:
            signal = "📉 BUY PUT"
        else:
            signal = "⚖️ WAIT"

        # ==========================================
        # UI
        # ==========================================
        colA, colB = st.columns(2)

        colA.metric("CALL (CE)", f"₹{ce_ltp}")
        colB.metric("PUT (PE)", f"₹{pe_ltp}")

        st.markdown("### 📊 Analysis")

        st.write(f"PCR: {pcr}")
        st.write(f"Strength: {strength}%")
        st.write(f"Support: {support}")
        st.write(f"Resistance: {resistance}")

        st.markdown(f"## ⚡ SIGNAL: {signal}")

    except Exception as e:
        st.error(f"Error: {e}")

    time.sleep(1)
    st.rerun()

# ==========================================
# OFFLINE
# ==========================================
else:
    col1.metric("SPOT", "₹0")
    col2.metric("ATM", "0")
    col3.metric("STATUS", "OFFLINE ❌")
