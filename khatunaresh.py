import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V64 | Pro Depth", layout="wide")
st.title("🏹 MKPV Ultra Sniper V64 | Institutional Depth Engine")

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'price_history', 'vol_history']:
    if key not in st.session_state:
        if key in ['price_history', 'vol_history']: st.session_state[key] = []
        else: st.session_state[key] = None

def get_time():
    try: return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except: return int(time.time())

@st.cache_data(ttl=3600)
def load_tokens():
    try:
        res = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=30)
        df = pd.DataFrame(res.json())
        return df[df['exch_seg'] == "NFO"]
    except: return None

# -- HELPER: GET STRIKE DEPTH --
def get_depth_score(obj, tokens, segment="NFO"):
    """Returns combined Bid Qty and Ask Qty for a list of tokens"""
    try:
        res = obj.getMarketData("FULL", {segment: tokens})
        t_bid, t_ask = 0, 0
        if res and res.get('status'):
            for item in res['data']['fetched']:
                t_bid += float(item.get('totalBuyQty', 0))
                t_ask += float(item.get('totalSellQty', 0))
        return t_bid, t_ask
    except: return 0, 0

# -- SIDEBAR --
st.sidebar.header("🕹️ Controls")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (07APR26)", "07APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 50, 1)
mpin = st.sidebar.text_input("MPIN", type="password")

if st.sidebar.button("🔑 Connect"):
    st.session_state.token_df = load_tokens()
    otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).at(get_time())
    obj = SmartConnect(api_key=API_KEY)
    login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected, st.session_state.obj = True, obj
        st.sidebar.success("✅ Connected!")
    else: st.sidebar.error("❌ Login Failed")

# -- MAIN ENGINE --
if st.session_state.connected:
    obj, df = st.session_state.obj, st.session_state.token_df
    
    # 1. BASE DATA (SPOT & INDEX DEPTH)
    idx_tok = "26000" if index == "NIFTY" else "26009"
    idx_res = obj.getMarketData("FULL", {"NSE": [idx_tok]})
    
    if idx_res['status']:
        m_data = idx_res['data']['fetched'][0]
        spot = float(m_data['ltp'])
        idx_bid, idx_ask = float(m_data['totalBuyQty']), float(m_data['totalSellQty'])
        idx_ratio = round(idx_bid/idx_ask, 2) if idx_ask > 0 else 1.0
        
        step = 50 if index == "NIFTY" else 100
        atm = int(round(spot / step) * step)
        
        # 2. STRIKE SELECTION (Support & Resistance Zones)
        # Resistance Zone: ATM CE + 2 OTM CE
        res_strikes = [f"{index}{expiry}{atm}CE", f"{index}{expiry}{atm+step}CE", f"{index}{expiry}{atm+(step*2)}CE"]
        # Support Zone: ATM PE + 2 OTM PE
        sup_strikes = [f"{index}{expiry}{atm}PE", f"{index}{expiry}{atm-step}PE", f"{index}{expiry}{atm-(step*2)}PE"]
        
        def get_toks(s_list):
            return [str(df[df['symbol'] == s].iloc[0]['token']) for s in s_list if not df[df['symbol'] == s].empty]

        ce_tokens, pe_tokens = get_toks(res_strikes), get_toks(sup_strikes)
        
        # 3. FETCH DEPTH FOR ZONES
        ce_bid, ce_ask = get_depth_score(obj, ce_tokens)
        pe_bid, pe_ask = get_depth_score(obj, pe_tokens)
        
        # 4. PRESSURE CALCULATIONS
        # High CE Ask = Strong Resistance | High PE Bid = Strong Support
        ce_pressure = round(ce_ask / ce_bid, 2) if ce_bid > 0 else 1.0
        pe_pressure = round(pe_bid / pe_ask, 2) if pe_ask > 0 else 1.0

        # -- DASHBOARD UI --
        st.subheader(f"📊 {index} Master Dashboard (Spot: ₹{spot})")
        c1, c2, c3 = st.columns(3)
        c1.metric("Index Orderbook Ratio", idx_ratio, delta="Bullish" if idx_ratio > 1 else "Bearish")
        c2.metric("Resistance (CE) Pressure", f"{ce_pressure}x", delta="Heavy Sellers" if ce_pressure > 1.1 else "Sellers Fleeing", delta_color="inverse")
        c3.metric("Support (PE) Pressure", f"{pe_pressure}x", delta="Heavy Buyers" if pe_pressure > 1.1 else "Weak Support")

        st.divider()

        # 5. ZONE ANALYSIS BARS
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🛡️ Support Zone (PE Strikes)")
            pe_p = int((pe_bid/(pe_bid+pe_ask))*100) if (pe_bid+pe_ask)>0 else 50
            st.write(f"Buyer Strength: {pe_p}%")
            st.progress(pe_p)
            st.caption(f"Bids: {int(pe_bid)} | Asks: {int(pe_ask)}")
            
        with col_b:
            st.markdown("#### 🏰 Resistance Zone (CE Strikes)")
            ce_p = int((ce_ask/(ce_bid+ce_ask))*100) if (ce_bid+ce_ask)>0 else 50
            st.write(f"Seller Strength: {ce_p}%")
            st.progress(ce_p)
            st.caption(f"Asks: {int(ce_ask)} | Bids: {int(ce_bid)}")

        # 6. SMART SNIPER LOGIC
        st.divider()
        st.subheader("🎯 Sniper Decision Matrix")
        
        buy_call = (idx_ratio > 1.1) and (pe_pressure > 1.3) and (ce_pressure < 1.0)
        buy_put = (idx_ratio < 0.9) and (ce_pressure > 1.3) and (pe_pressure < 1.0)
        
        m1, m2 = st.columns(2)
        if buy_call:
            m1.success("🚀 SIGNAL: STRONG BUY CALL (Support is solid, Resistance melting)")
        else:
            m1.info("Wait for Call Confirmation...")
            
        if buy_put:
            m2.error("🩸 SIGNAL: STRONG BUY PUT (Resistance heavy, Support breaking)")
        else:
            m2.info("Wait for Put Confirmation...")

        # 7. AUTO REFRESH
        time.sleep(2)
        st.rerun()

    else:
        st.error("Market Data Fetch Error")
