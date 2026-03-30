import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import pandas as pd
import time

# --- 1. INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None

# --- CONFIG ---
FIXED_CLIENT_ID = "PS1646259" # Aapka exact Client ID jo video mein dikha
st.set_page_config(page_title="GRK SNIPER V9", layout="wide")

# --- 2. TOKEN ENGINE (With Error Bypass) ---
@st.cache_data(ttl=3600)
def fetch_tokens_safe():
    url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            full_df = pd.DataFrame(r.json())
            return full_df[full_df['exch_seg'] == 'NFO']
        return None
    except:
        return None

# --- SIDEBAR UI ---
st.sidebar.title("🎯 GRK SNIPER V9")
idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_input = st.sidebar.text_input("Expiry (DDMMMYY)", value="02APR26").upper()

st.sidebar.markdown("---")
if st.sidebar.button("🛠️ Load Tokens"):
    with st.spinner("Downloading Tokens..."):
        st.session_state.token_df = fetch_tokens_safe()
        if st.session_state.token_df is not None:
            st.sidebar.success(f"✅ {len(st.session_state.token_df)} Symbols Loaded")
        else:
            st.sidebar.warning("⚠️ Server Down! Using Manual Mode.")

# --- LOGIN SECTION ---
api_key = st.sidebar.text_input("SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)
totp_key = st.sidebar.text_input("TOTP Secret", value="W6SCERQJX4RSU6TXECROABI7TA", type="password")

if st.sidebar.button("🚀 Connect Bot"):
    try:
        otp = pyotp.TOTP(totp_key.strip().replace(" ", "")).now()
        obj = SmartConnect(api_key=api_key.strip())
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Bot Live!")
        else:
            st.sidebar.error(f"❌ Login Error: {data['message']}")
    except Exception as e:
        st.sidebar.error(f"❌ Connection Error: {e}")

# --- DASHBOARD ---
st.title("🏹 MKPV SNIPER | LIVE TERMINAL")
st.divider()

if st.session_state.connected:
    # 1. LIVE SPOT FETCH
    t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
    t_tok = "26000" if idx == "NIFTY" else "26009"
    
    spot_res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
    
    if spot_res['status']:
        ltp = float(spot_res['data']['ltp'])
        step = 50 if idx == "NIFTY" else 100
        atm = int(round(ltp / step) * step)
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"SPOT {idx}", f"₹{ltp}", delta="LIVE")
        c2.metric("ATM STRIKE", atm)
        c3.metric("STATUS", "STABLE ✅")

        # 2. TOKEN SEARCH LOGIC
        search_sym = f"{idx}{expiry_input}{atm}"
        
        col_ce, col_pe = st.columns(2)
        
        # Safe Search to prevent Crash
        if st.session_state.token_df is not None:
            df = st.session_state.token_df
            ce_data = df[df['symbol'] == f"{search_sym}CE"]
            pe_data = df[df['symbol'] == f"{search_sym}PE"]
            
            with col_ce:
                if not ce_data.empty:
                    st.success(f"🟢 {ce_data.iloc[0]['symbol']}")
                    st.write(f"**Token:** `{ce_data.iloc[0]['token']}`")
                else: st.warning(f"CE Token Not Found for {search_sym}")

            with col_pe:
                if not pe_data.empty:
                    st.error(f"🔴 {pe_data.iloc[0]['symbol']}")
                    st.write(f"**Token:** `{pe_data.iloc[0]['token']}`")
                else: st.warning(f"PE Token Not Found for {search_sym}")
        else:
            st.info("💡 Tokens load nahi hue hain. Sidebar mein 'Load Tokens' dabayein.")

    time.sleep(1)
    st.rerun()
else:
    st.warning("👈 Please Login from the sidebar to see live data.")
