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

st.set_page_config(page_title="GRK SNIPER PRO MAX", layout="wide")

# ==========================================
# SESSION STATE
# ==========================================
if 'obj' not in st.session_state:
    st.session_state.obj = None

if 'connected' not in st.session_state:
    st.session_state.connected = False

if 'df' not in st.session_state:
    st.session_state.df = None

# ==========================================
# SAFE TOKEN LOAD
# ==========================================
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        return pd.DataFrame(res.json())
    except:
        return None

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🚀 GRK SNIPER PRO MAX")

idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (DDMMMYYYY)", "02APR2026")

api_key = st.sidebar.text_input("API Key")
mpin = st.sidebar.text_input("MPIN", type="password")
totp = st.sidebar.text_input("TOTP Secret", type="password")

# ==========================================
# START BOT
# ==========================================
if st.sidebar.button("Start Bot"):

    df = load_tokens()
    if df is None:
        st.sidebar.error("❌ Token load failed")
        st.stop()

    st.session_state.df = df

    try:
        otp = pyotp.TOTP(totp).now()
        obj = SmartConnect(api_key)
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)

        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Connected")
        else:
            st.sidebar.error("❌ Login Failed")

    except Exception as e:
        st.sidebar.error(f"❌ Login Error: {e}")

# ==========================================
# MAIN UI
# ==========================================
st.title("🚀 MKPV SNIPER PRO MAX")
st.divider()

col1, col2, col3 = st.columns(3)

# ==========================================
# LIVE LOGIC
# ==========================================
if st.session_state.connected:

    obj = st.session_state.obj
    df = st.session_state.df

    try:
        # INDEX DATA
        sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        tok = "26000" if idx == "NIFTY" else "26009"

        ltp_res = obj.ltpData("NSE", sym, tok)

        if not ltp_res['status']:
            st.error("❌ Session expired. Restart bot.")
            st.session_state.connected = False
            st.stop()

        spot = ltp_res['data']['ltp']
        atm = round(spot / 50) * 50

        col1.metric("SPOT", f"₹{spot}")
        col2.metric("ATM", atm)
        col3.metric("STATUS", "STABLE ✅")

        st.markdown("### 📊 ATM Option Chain")

        # ==========================================
        # FIX EXPIRY FORMAT
        # ==========================================
        expiry_short = expiry[:-4] + expiry[-2:]
        base = f"NIFTY{expiry_short}{atm}"

        ce_row = df[df['symbol'].str.contains(base + "CE", na=False)]
        pe_row = df[df['symbol'].str.contains(base + "PE", na=False)]

        if ce_row.empty or pe_row.empty:
            st.warning("⚠️ Symbols not found. Check expiry format.")
            st.stop()

        ce = ce_row.iloc[0]
        pe = pe_row.iloc[0]

        # ==========================================
        # FETCH CE/PE
        # ==========================================
        ce_data = obj.ltpData("NFO", ce['symbol'], ce['token'])
        pe_data = obj.ltpData("NFO", pe['symbol'], pe['token'])

        ce_ltp = ce_data['data']['ltp'] if ce_data['status'] else 0
        pe_ltp = pe_data['data']['ltp'] if pe_data['status'] else 0

        # ==========================================
        # ANALYSIS
        # ==========================================
        ce_oi = ce_data['data'].get('openInterest', 0) if ce_data['status'] else 0
        pe_oi = pe_data['data'].get('openInterest', 0) if pe_data['status'] else 0

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
        # UI DISPLAY
        # ==========================================
        colA, colB = st.columns(2)

        colA.metric("CALL LTP", f"₹{ce_ltp}")
        colB.metric("PUT LTP", f"₹{pe_ltp}")

        st.markdown("### 📊 Analysis")

        st.write(f"PCR: {pcr}")
        st.write(f"Strength: {strength}%")
        st.write(f"Support: {support}")
        st.write(f"Resistance: {resistance}")

        st.markdown(f"## ⚡ SIGNAL: {signal}")

    except Exception as e:
        st.error(f"❌ Runtime Error: {e}")

    time.sleep(1)
    st.rerun()

# ==========================================
# OFFLINE
# ==========================================
else:
    col1.metric("SPOT", "₹0")
    col2.metric("ATM", "0")
    col3.metric("STATUS", "OFFLINE ❌")
