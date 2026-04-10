import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V67 | Systematic", layout="wide")

# --- FIXED CSS ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #00ffcc; }
    .stProgress > div > div > div > div { background-color: #10b981; }
    </style>
    """, unsafe_allow_html=True) # FIXED: unsafe_allow_html

# -- SESSION STATE INITIALIZATION --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'price_history' not in st.session_state: st.session_state.price_history = []
if 'active_trade' not in st.session_state: st.session_state.active_trade = None

@st.cache_data(ttl=3600)
def load_tokens():
    try:
        res = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=30)
        df = pd.DataFrame(res.json())
        return df[df['exch_seg'] == "NFO"]
    except: return None

# -- SIDEBAR --
st.sidebar.title("🚀 Sniper Controls")
index = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g., 16APR26)", "16APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 50, 1)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trading")
mpin = st.sidebar.text_input("MPIN", type="password")

if st.sidebar.button("🔑 Secure Login"):
    st.session_state.token_df = load_tokens()
    otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).at(int(time.time()))
    obj = SmartConnect(api_key=API_KEY)
    login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected, st.session_state.obj = True, obj
        st.sidebar.success("✅ System Online")
    else:
        st.sidebar.error("❌ Login Failed")

# -- SYSTEMATIC ENGINE --
if st.session_state.connected:
    obj, df = st.session_state.obj, st.session_state.token_df
    step = 50 if index == "NIFTY" else 100
    
    try:
        # 1. LIVE DATA FETCH
        idx_tok = "26000" if index == "NIFTY" else "26009"
        res = obj.ltpData("NSE", index, idx_tok)
        
        if res and res.get('status'):
            spot = float(res['data']['ltp'])
            atm = int(round(spot / step) * step)

            # 2. GENERATE 20 STRIKE TOKENS (ATM ± 10)
            tokens_to_fetch = []
            token_map = {}
            for i in range(-10, 11):
                for sfx in ["CE", "PE"]:
                    sym = f"{index}{expiry}{atm+(i*step)}{sfx}"
                    t_row = df[df['symbol'] == sym]
                    if not t_row.empty:
                        tk = str(t_row.iloc[0]['token'])
                        tokens_to_fetch.append(tk)
                        token_map[tk] = {"type": sfx, "strike": atm+(i*step)}

            # 3. FETCH FULL DEPTH & OI
            full_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            master_list = []
            ce_oi = pe_oi = ce_bid = ce_ask = pe_bid = pe_ask = 0
            
            if full_data and full_data.get('status'):
                for item in full_data['data']['fetched']:
                    m = token_map.get(item['symbolToken'])
                    if not m: continue
                    
                    b, a, o = float(item.get('totalBuyQty', 0)), float(item.get('totalSellQty', 0)), float(item.get('opnInterest', 0))
                    
                    if m['type'] == "CE": 
                        ce_oi += o; ce_bid += b; ce_ask += a
                    else: 
                        pe_oi += o; pe_bid += b; pe_ask += a
                        
                    master_list.append({"Strike": m['strike'], "Type": m['type'], "Bids": b, "Asks": a, "OI": o})

            pcr = round(pe_oi/ce_oi, 2) if ce_oi > 0 else 1.0
            
            # --- UI SECTION 1: SYSTEM PULSE ---
            st.title(f"🏹 {index} SYSTEMATIC SNIPER V67")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LIVE SPOT", f"₹{spot}")
            c2.metric("GLOBAL PCR", pcr, delta="Bullish" if pcr > 1 else "Bearish")
            c3.metric("PUT DEMAND (Bids)", f"{int(pe_bid)}")
            c4.metric("CALL SUPPLY (Asks)", f"{int(ce_ask)}")
            
            st.divider()

            # --- UI SECTION 2: BATTLEGROUND (TABLES) ---
            t1, t2 = st.columns(2)
            df_main = pd.DataFrame(master_list)
            with t1:
                st.subheader("🔴 Call Resistance (Supply Layer)")
                st.dataframe(df_main[df_main['Type']=="CE"].sort_values("Strike").tail(10), hide_index=True, use_container_width=True)
            with t2:
                st.subheader("🟢 Put Support (Demand Layer)")
                st.dataframe(df_main[df_main['Type']=="PE"].sort_values("Strike").head(10), hide_index=True, use_container_width=True)

            # --- UI SECTION 3: SYSTEMATIC CHECKLIST ---
            st.divider()
            st.subheader("📋 Sniper Execution Checklist")
            
            check_bull = {
                "PCR > 1.0 (Bullish Sentiment)": pcr > 1.0,
                "Bids > Asks (Buying Pressure)": pe_bid > ce_ask,
                "Strong Support Base (PE Bids)": pe_bid > (pe_ask * 1.2)
            }
            
            check_bear = {
                "PCR < 1.0 (Bearish Sentiment)": pcr < 1.0,
                "Asks > Bids (Selling Pressure)": ce_ask > pe_bid,
                "Strong Resistance Wall (CE Asks)": ce_ask > (ce_bid * 1.2)
            }

            l1, l2 = st.columns(2)
            with l1:
                st.markdown("### 🏹 Call Setup")
                for text, val in check_bull.items():
                    st.write(f"{'✅' if val else '❌'} {text}")
                ce_score = sum(check_bull.values())
                st.progress(ce_score/len(check_bull))
                
            with l2:
                st.markdown("### 🏹 Put Setup")
                for text, val in check_bear.items():
                    st.write(f"{'✅' if val else '❌'} {text}")
                pe_score = sum(check_bear.values())
                st.progress(pe_score/len(check_bear))

            # --- REFRESH LOGIC ---
            time.sleep(2)
            st.rerun()

    except Exception as e:
        st.warning(f"Connecting to Data Stream... ({e})")
        time.sleep(2)
        st.rerun()
