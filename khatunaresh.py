import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V66 | Ultra Deep Engine", layout="wide")
st.title("🏹 MKPV Ultra Sniper V66 | Dual Force Deep Engine")

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history', 'vol_history']:
    if key not in st.session_state:
        if key in ['price_history', 'vol_history', 'trade_history']: st.session_state[key] = []
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

# -- SIDEBAR CONTROLS --
st.sidebar.title("⚙️ Robot Controls")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED", value=True)
auto_trade = st.sidebar.checkbox("🤖 Auto-Trade Mode", value=False)
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 16APR26)", "16APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 50, 1)
tgt = st.sidebar.number_input("Target Points", 40.0, step=5.0)
sl = st.sidebar.number_input("Stoploss Points", 20.0, step=5.0)
min_vix = st.sidebar.number_input("Min VIX", value=11.5)
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
if st.session_state.connected and live_feed:
    obj, df = st.session_state.obj, st.session_state.token_df
    step = 50 if index == "NIFTY" else 100
    qty = (50 if index == "NIFTY" else 15) * lots

    try:
        # 1. FETCH BASE DATA
        idx_tok = "26000" if index == "NIFTY" else "26009"
        res = obj.ltpData("NSE", index, idx_tok)
        vix_res = obj.ltpData("NSE", "INDIA VIX", "26017")
        
        if res and res.get('status'):
            spot = float(res['data']['ltp'])
            live_vix = float(vix_res['data']['ltp']) if vix_res.get('status') else 12.0
            atm = int(round(spot / step) * step)

            # 2. GENERATE 20 STRIKES (ATM ± 10)
            strike_range = range(-10, 11)
            tokens_to_fetch = []
            token_map = {}
            for i in strike_range:
                for suffix in ["CE", "PE"]:
                    sym = f"{index}{expiry}{atm + (i * step)}{suffix}"
                    row = df[df['symbol'] == sym]
                    if not row.empty:
                        t = str(row.iloc[0]['token'])
                        tokens_to_fetch.append(t)
                        token_map[t] = {"sym": sym, "type": suffix, "strike": atm + (i * step)}

            # 3. FETCH FULL MARKET DEPTH & OI
            full_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            depth_list = []
            total_ce_oi = total_pe_oi = 0
            ce_atm_ltp = pe_atm_ltp = 0

            if full_data.get('status'):
                for item in full_data['data']['fetched']:
                    t_info = token_map.get(item['symbolToken'])
                    if not t_info: continue
                    
                    bid = float(item.get('totalBuyQty', 0))
                    ask = float(item.get('totalSellQty', 0))
                    oi = float(item.get('opnInterest', 0))
                    ltp = float(item.get('ltp', 0))
                    
                    if t_info['type'] == "CE": 
                        total_ce_oi += oi
                        if t_info['strike'] == atm: ce_atm_ltp = ltp
                    else: 
                        total_pe_oi += oi
                        if t_info['strike'] == atm: pe_atm_ltp = ltp

                    depth_list.append({
                        "Strike": t_info['strike'], "Type": t_info['type'], 
                        "LTP": ltp, "Bids": bid, "Asks": ask, "OI": oi,
                        "Pressure": round(bid/ask, 2) if ask > 0 else 1.0
                    })

            # 4. INDICATORS CALCULATION
            pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0
            st.session_state.price_history.append(spot)
            if len(st.session_state.price_history) > 30: st.session_state.price_history.pop(0)
            sma = sum(st.session_state.price_history) / len(st.session_state.price_history)

            # 5. UI DASHBOARD
            st.subheader(f"📊 {index} Institutional Dashboard | Spot: ₹{spot}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("India VIX", live_vix, delta="Safe" if live_vix > min_vix else "Low Vol")
            m2.metric("Global PCR", pcr, delta="Bullish" if pcr > 1 else "Bearish")
            m3.metric("Trend (SMA 30)", round(sma, 2))
            m4.metric("ATM CE/PE LTP", f"{ce_atm_ltp} / {pe_atm_ltp}")

            # 6. DEEP DATA TABLES
            master_df = pd.DataFrame(depth_list)
            col_ce, col_pe = st.columns(2)
            with col_ce:
                st.markdown("### 🔴 CALL Resistance Depth (Top 10)")
                st.dataframe(master_df[master_df['Type']=="CE"].sort_values("Strike").tail(10), use_container_width=True)
            with col_pe:
                st.markdown("### 🟢 PUT Support Depth (Top 10)")
                st.dataframe(master_df[master_df['Type']=="PE"].sort_values("Strike").head(10), use_container_width=True)

            # 7. 5-STAR SNIPER LOGIC
            st.divider()
            c_price = spot > sma
            c_oi = pcr > 1.0
            c_depth = master_df[master_df['Type']=="PE"]['Bids'].sum() > master_df[master_df['Type']=="CE"]['Asks'].sum()
            
            ce_score = sum([c_price, c_oi, c_depth, ce_atm_ltp > pe_atm_ltp])
            pe_score = sum([not c_price, not c_oi, not c_depth, pe_atm_ltp > ce_atm_ltp])

            s1, s2 = st.columns(2)
            s1.metric("CALL Sniper Confidence", f"{(ce_score/4)*100}%")
            s2.metric("PUT Sniper Confidence", f"{(pe_score/4)*100}%")

            # 8. AUTO-TRADE EXECUTION
            if st.session_state.active_trade is None and auto_trade and live_vix > min_vix:
                if ce_score >= 3:
                    st.success("🤖 Auto-Buying CALL...")
                    st.session_state.active_trade = {"type": "CE", "entry": spot, "target": spot+tgt, "sl": spot-sl}
                elif pe_score >= 3:
                    st.error("🤖 Auto-Buying PUT...")
                    st.session_state.active_trade = {"type": "PE", "entry": spot, "target": spot-tgt, "sl": spot+sl}
            
            # 9. ACTIVE TRADE TRACKING
            if st.session_state.active_trade:
                t = st.session_state.active_trade
                pnl = round(spot - t['entry'] if t['type']=="CE" else t['entry'] - spot, 2)
                st.info(f"🚀 Active {t['type']} Trade | P&L: {pnl} Pts")
                if st.button("🚨 Emergency Exit"): st.session_state.active_trade = None

            time.sleep(2)
            st.rerun()

    except Exception as e:
        st.error(f"Engine Error: {e}")
        time.sleep(5)
        st.rerun()
