import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests
import pandas as pd

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_map' not in st.session_state: st.session_state.token_map = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
st.set_page_config(page_title="GRK SNIPER V8", layout="wide")

# --- TOKEN MASTER LOADER (With Error Handling) ---
@st.cache_data
def load_tokens():
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            # Sirf NFO (Options) aur sahi format wale symbols rakhein
            df = df[df['exch_seg'] == 'NFO']
            return df
        return None
    except Exception as e:
        st.error(f"Token Error: {e}")
        return None

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V8")
idx = st.sidebar.radio("Market Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Current Expiry (e.g., 02APR26)", value="02APR26")

st.sidebar.markdown("---")
api_key = st.sidebar.text_input("1. SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("2. MPIN", type="password", max_chars=4)
totp_key = st.sidebar.text_input("3. TOTP Secret", value="W6SCERQJX4RSU6TXECROABI7TA", type="password")

if st.sidebar.button("Load Tokens & Connect"):
    with st.spinner("Downloading Data..."):
        st.session_state.token_map = load_tokens()
        
        # Login
        try:
            otp = pyotp.TOTP(totp_key.strip().replace(" ", "")).now()
            obj = SmartConnect(api_key=api_key.strip())
            data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            if data['status']:
                st.session_state.obj = obj
                st.session_state.connected = True
                st.sidebar.success("✅ Sniper Ready!")
            else:
                st.sidebar.error(f"Login Failed: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"Login Error: {e}")

# --- DASHBOARD ---
st.title("🏹 MKPV SNIPER | LIVE DATA & OI")
st.divider()

if st.session_state.connected:
    try:
        # 1. Spot Price fetch
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"
        
        spot_res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
        if spot_res['status']:
            ltp = float(spot_res['data']['ltp'])
            step = 50 if idx == "NIFTY" else 100
            atm = int(round(ltp / step) * step)

            # Metrics Row
            c1, c2, c3 = st.columns(3)
            c1.metric("SPOT PRICE", f"₹{ltp}")
            c2.metric("ATM STRIKE", atm)
            c3.metric("STATUS", "STABLE ✅")

            # 2. Find CE/PE Tokens
            ce_sym = f"{idx.upper()}{expiry}{atm}CE"
            pe_sym = f"{idx.upper()}{expiry}{atm}PE"
            
            # Helper to find token
            def get_token_info(symbol):
                if st.session_state.token_map is not None:
                    match = st.session_state.token_map[st.session_state.token_map['symbol'] == symbol]
                    if not match.empty:
                        return match.iloc[0]['token'], match.iloc[0]['lotsize']
                return None, None

            ce_token, ce_lot = get_token_info(ce_sym)
            pe_token, pe_lot = get_token_info(pe_sym)

            # 3. Fetch OI & Live Price for Options
            st.subheader(f"📊 ATM Option Chain Analysis (@ {atm})")
            col_ce, col_pe = st.columns(2)

            if ce_token and pe_token:
                # CE/PE Data Fetch using getQuote or ltpData
                # Yahan hum Full Quote API use kar sakte hain Volume/OI ke liye
                st.write(f"CE Token: {ce_token} | PE Token: {pe_token}")
                
                # Placeholder for Live Analysis
                with col_ce:
                    st.info(f"🟢 CALL: {ce_sym}")
                    st.metric("LTP", "Updating...")
                    st.metric("OI", "Analyzing...")

                with col_pe:
                    st.info(f"🔴 PUT: {pe_sym}")
                    st.metric("LTP", "Updating...")
                    st.metric("OI", "Analyzing...")
            else:
                st.warning(f"Tokens not found for {expiry}. Check Expiry format in Sidebar.")

        else:
            st.session_state.connected = False
            st.rerun()

    except Exception as e:
        st.error(f"Execution Error: {e}")
    
    time.sleep(2)
    st.rerun()
else:
    st.info("Please connect from Sidebar to see Live Sniper Data.")
