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

st.set_page_config(page_title="GRK SNIPER PRO", layout="wide")

# ==========================================
# SESSION
# ==========================================
if 'obj' not in st.session_state:
    st.session_state.obj = None

if 'connected' not in st.session_state:
    st.session_state.connected = False

if 'df' not in st.session_state:
    st.session_state.df = None

# ==========================================
# LOAD TOKEN MASTER
# ==========================================
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    data = requests.get(url).json()
    return pd.DataFrame(data)

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🚀 GRK SNIPER PRO")

idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry", "02APR2026")

api_key = st.sidebar.text_input("API Key")
mpin = st.sidebar.text_input("MPIN", type="password")
totp = st.sidebar.text_input("TOTP Secret", type="password")

if st.sidebar.button("Start Bot"):

    st.session_state.df = load_tokens()

    otp = pyotp.TOTP(totp).now()
    obj = SmartConnect(api_key)
    data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)

    if data['status']:
        st.session_state.obj = obj
        st.session_state.connected = True
        st.sidebar.success("✅ Connected")

# ==========================================
# MAIN
# ==========================================
st.title("🚀 MKPV SNIPER PRO MAX")

if st.session_state.connected:

    obj = st.session_state.obj
    df = st.session_state.df

    # INDEX
    sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
    tok = "26000" if idx == "NIFTY" else "26009"

    ltp = obj.ltpData("NSE", sym, tok)['data']['ltp']
    atm = round(ltp / 50) * 50

    st.metric("SPOT", ltp)
    st.metric("ATM", atm)

    # ==========================================
    # SYMBOL FIX
    # ==========================================
    expiry_short = expiry[:-4] + expiry[-2:]
    base = f"NIFTY{expiry_short}"

    ce_df = df[df['symbol'].str.contains(base + str(atm) + "CE", na=False)]
    pe_df = df[df['symbol'].str.contains(base + str(atm) + "PE", na=False)]

    if ce_df.empty or pe_df.empty:
        st.error("❌ Symbol not found")
        st.stop()

    ce = ce_df.iloc[0]
    pe = pe_df.iloc[0]

    # ==========================================
    # FETCH DATA
    # ==========================================
    ce_data = obj.ltpData("NFO", ce['symbol'], ce['token'])
    pe_data = obj.ltpData("NFO", pe['symbol'], pe['token'])

    ce_ltp = ce_data['data']['ltp']
    pe_ltp = pe_data['data']['ltp']

    # Fake OI (Angel free API me OI direct nahi milta reliably)
    ce_oi = ce_data['data'].get('openInterest', 0)
    pe_oi = pe_data['data'].get('openInterest', 0)

    # ==========================================
    # ANALYSIS
    # ==========================================
    total_oi = ce_oi + pe_oi + 1
    pcr = pe_oi / total_oi

    strength = round((pe_oi / total_oi) * 100)

    if pcr > 1:
        signal = "📈 BUY CALL"
    elif pcr < 0.7:
        signal = "📉 BUY PUT"
    else:
        signal = "⚖️ WAIT"

    support = atm if pe_oi > ce_oi else atm - 50
    resistance = atm if ce_oi > pe_oi else atm + 50

    # ==========================================
    # UI
    # ==========================================
    col1, col2 = st.columns(2)

    col1.metric("CALL LTP", ce_ltp)
    col2.metric("PUT LTP", pe_ltp)

    st.markdown("### 📊 Analysis")

    st.write(f"PCR: {round(pcr,2)}")
    st.write(f"Strength: {strength}%")
    st.write(f"Support: {support}")
    st.write(f"Resistance: {resistance}")

    st.markdown(f"## ⚡ SIGNAL: {signal}")

    # ==========================================
    # AUTO REFRESH
    # ==========================================
    time.sleep(1)
    st.rerun()
