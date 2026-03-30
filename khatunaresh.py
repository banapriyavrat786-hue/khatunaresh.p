import streamlit as st
from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
import time
from datetime import datetime

# ================= CONFIG =================
API_KEY = "MT72qa1q"
CLIENT_ID = "P51646259"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(layout="wide")

# ================= LOGIN =================
st.sidebar.title("🚀 GRK SNIPER PRO MAX")

mpin = st.sidebar.text_input("Enter MPIN", type="password")

if st.sidebar.button("Connect"):
    try:
        otp = pyotp.TOTP(TOTP_SECRET).now()
        obj = SmartConnect(api_key=API_KEY)
        data = obj.generateSession(CLIENT_ID, mpin, otp)

        if data['status']:
            st.session_state.obj = obj
            st.success("✅ Connected")
        else:
            st.error(data['message'])

    except Exception as e:
        st.error(e)

# ================= LOAD TOKEN =================
@st.cache_data(ttl=3600)
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    data = requests.get(url).json()
    df = pd.DataFrame(data)

    df = df[df['exch_seg'] == 'NFO']
    df = df[df['instrumenttype'] == 'OPTIDX']
    df = df[df['name'] == 'NIFTY']

    # FIX datetime
    df['expiry'] = pd.to_datetime(df['expiry'], errors='coerce')
    df = df.dropna(subset=['expiry'])

    return df

# ================= MAIN =================
st.title("🚀 MKPV SNIPER PRO MAX")

if "obj" in st.session_state:

    obj = st.session_state.obj

    # ===== GET SPOT =====
    try:
        spot = obj.ltpData("NSE", "Nifty 50", "26000")
        spot_price = spot['data']['ltp']
    except:
        spot_price = 0

    atm = round(spot_price / 50) * 50

    col1, col2, col3 = st.columns(3)
    col1.metric("Spot", f"₹{spot_price}")
    col2.metric("ATM", atm)
    col3.metric("Status", "LIVE ✅")

    # ===== TOKEN DATA =====
    df = load_tokens()

    # 👉 nearest expiry select karo (AUTO FIX)
    expiry = df['expiry'].min()

    df_exp = df[df['expiry'] == expiry]

    # 👉 correct strike filter
    df_strike = df_exp[df_exp['strike'] == atm * 100]

    if df_strike.empty:
        st.error("❌ Strike not found → nearest strike use kar raha hu")

        df_exp['diff'] = abs(df_exp['strike'] - atm*100)
        df_strike = df_exp.sort_values('diff').head(2)

    # ===== CE & PE =====
    ce = df_strike[df_strike['symbol'].str.contains("CE")].head(1)
    pe = df_strike[df_strike['symbol'].str.contains("PE")].head(1)

    col1, col2 = st.columns(2)

    # ===== CE DATA =====
    if not ce.empty:
        ce_symbol = ce.iloc[0]['symbol']
        ce_token = ce.iloc[0]['token']

        try:
            ce_ltp = obj.ltpData("NFO", ce_symbol, ce_token)
            ce_price = ce_ltp['data']['ltp']
        except:
            ce_price = 0

        col1.metric("CALL CE", ce_price)

    # ===== PE DATA =====
    if not pe.empty:
        pe_symbol = pe.iloc[0]['symbol']
        pe_token = pe.iloc[0]['token']

        try:
            pe_ltp = obj.ltpData("NFO", pe_symbol, pe_token)
            pe_price = pe_ltp['data']['ltp']
        except:
            pe_price = 0

        col2.metric("PUT PE", pe_price)

    # ===== ANALYSIS =====
    st.subheader("📊 Smart Analysis")

    if ce_price > pe_price:
        st.success("📈 CALL STRONG (Resistance Zone)")
    else:
        st.error("📉 PUT STRONG (Support Zone)")

    total = ce_price + pe_price if ce_price + pe_price != 0 else 1

    ce_pct = (ce_price / total) * 100
    pe_pct = (pe_price / total) * 100

    st.progress(int(ce_pct))
    st.write(f"CALL Strength: {round(ce_pct,2)}%")

    st.progress(int(pe_pct))
    st.write(f"PUT Strength: {round(pe_pct,2)}%")

else:
    st.warning("⚠️ Login first")
