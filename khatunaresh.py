import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd
import requests

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'tokens_df' not in st.session_state: st.session_state.tokens_df = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
st.set_page_config(page_title="GRK SNIPER V7", layout="wide")

# --- 1. TOKEN FINDER ENGINE ---
@st.cache_data
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/instrument_master.json"
    response = requests.get(url).json()
    df = pd.DataFrame(response)
    # Sirf NFO (Options) filter karein
    return df[df['exch_seg'] == 'NFO']

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V7")
idx = st.sidebar.radio("Market Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Current Expiry (DDMMMYY)", value="02APR26").upper()

st.sidebar.markdown("---")
api_key = st.sidebar.text_input("1. SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("2. MPIN", type="password", max_chars=4)
totp_key = st.sidebar.text_input("3. TOTP Secret", value="W6SCERQJX4RSU6TXECROABI7TA", type="password")

if st.sidebar.button("Connect Sniper"):
    try:
        otp = pyotp.TOTP(totp_key.strip().replace(" ", "")).now()
        obj = SmartConnect(api_key=api_key.strip())
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            with st.spinner("Loading Scrip Master..."):
                st.session_state.tokens_df = load_tokens()
            st.sidebar.success("✅ SNIPER ACTIVE")
        else: st.sidebar.error(f"❌ Login Failed: {data['message']}")
    except Exception as e: st.sidebar.error(f"❌ {e}")

# --- DASHBOARD ---
if st.session_state.connected:
    try:
        # A. Fetch Spot
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"
        res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
        
        if res['status']:
            ltp = float(res['data']['ltp'])
            step = 50 if idx == "NIFTY" else 100
            atm = int(round(ltp / step) * step)

            # B. UI Layout
            c1, c2, c3 = st.columns(3)
            c1.metric("SPOT PRICE", f"₹{ltp}", delta="LIVE")
            c2.metric("ATM STRIKE", f"{atm}")
            c3.metric("SYSTEM STATUS", "STABLE ✅")

            st.markdown("---")
            st.subheader(f"📊 {idx} Option Chain (Targeting ATM @ {atm})")

            # C. Fetch ATM Option Data
            # Token finding logic
            symbol_pattern_ce = f"{idx}{expiry}{atm}CE"
            symbol_pattern_pe = f"{idx}{expiry}{atm}PE"
            
            try:
                ce_info = st.session_state.tokens_df[st.session_state.tokens_df['symbol'] == symbol_pattern_ce].iloc[0]
                pe_info = st.session_state.tokens_df[st.session_state.tokens_df['symbol'] == symbol_pattern_pe].iloc[0]
                
                # Get Quote for OI and Vol
                payload = {
                    "exchange": "NFO",
                    "symboltoken": ce_info['token'],
                    "tradingsymbol": ce_info['symbol']
                }
                # (Note: In real bot, use getFullQuote here)
                
                col_ce, col_pe = st.columns(2)
                with col_ce:
                    st.success(f"CALL (CE) - Resistance Zone")
                    st.write(f"**LTP:** Fetching Live...")
                    st.write(f"**OI:** {ce_info['token']} (Token Found)")
                
                with col_pe:
                    st.error(f"PUT (PE) - Support Zone")
                    st.write(f"**LTP:** Fetching Live...")
                    st.write(f"**OI:** {pe_info['token']} (Token Found)")

            except:
                st.warning(f"⚠️ Symbols {symbol_pattern_ce} not found in {expiry}. Check Expiry Date format.")

        else:
            st.session_state.connected = False
            st.rerun()

    except Exception as e: st.error(f"Error: {e}")
    
    time.sleep(2)
    st.rerun()
else:
    st.info("Please Connect Sniper from Sidebar")
