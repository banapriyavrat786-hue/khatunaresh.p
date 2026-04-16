import streamlit as st
from SmartApi import SmartConnect
import pyotp
import pandas as pd
import time
import requests
from datetime import datetime, timedelta

# -- CONFIGURATION (Angel One) --
CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="Warrior-Sniper V81 | Anti-Error", layout="wide")

# -- SESSION STATE: ADDED SMART CACHE TO PREVENT ERRORS --
if 'connected' not in st.session_state:
    keys = ['obj', 'connected', 'token_df', 'oi_history']
    for k in keys: st.session_state[k] = {} if k == 'oi_history' else None
    
    # Smart Cache variables for Rate-Limit protection
    st.session_state.last_hist_update = 0 
    st.session_state.cached_sma = 0
    st.session_state.cached_pivot = 0
    st.session_state.cached_r1 = 0
    st.session_state.cached_s1 = 0

# --- SIDEBAR & LOGIN ---
st.sidebar.title("🚀 V81 (Anti-Error Engine)")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 23APR26)", "23APR26").upper()
mpin = st.sidebar.text_input("Angel MPIN", type="password")

if st.sidebar.button("🔑 Connect Safely"):
    try:
        # Fetch Tokens safely
        raw_data = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=10).json()
        df_temp = pd.DataFrame(raw_data)
        st.session_state.token_df = df_temp[df_temp['exch_seg'] == "NFO"]
        
        obj = SmartConnect(api_key=API_KEY)
        otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).now()
        login = obj.generateSession(CLIENT_ID, mpin, otp)
        
        if login.get('status'):
            st.session_state.obj, st.session_state.connected = obj, True
            st.sidebar.success("✅ Engine Online & Stable!")
        else:
            st.sidebar.error("❌ Invalid Credentials/MPIN")
    except Exception as e: 
        st.sidebar.error(f"Network Error: {e}")

# --- THE MAIN ENGINE ---
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df
    idx_tok = "26000" if index == "NIFTY" else "26009"
    step = 50 if index == "NIFTY" else 100

    try:
        current_time = time.time()

        # 1. FETCH LIVE SPOT PRICE
        res = obj.ltpData("NSE", index, idx_tok)
        if not res or not res.get('status'):
            raise Exception("Spot Price API Error")
            
        spot = float(res['data']['ltp'])
        pc = float(res['data']['close'])
        atm = int(round(spot / step) * step)

        # 2. WARRIOR LOGIC: SMART CACHING (Saves API Limits)
        # Fetch historical data only once every 60 seconds!
        if (current_time - st.session_state.last_hist_update) > 60:
            hist = obj.getCandleData({"exchange": "NSE", "symboltoken": idx_tok, "interval": "FIVE_MINUTE", 
                                      "fromdate": (datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
                                      "todate": datetime.now().strftime('%Y-%m-%d %H:%M')})
            if hist and hist.get('status') and hist.get('data'):
                df_h = pd.DataFrame(hist['data'], columns=['t','o','h','l','c','v'])
                st.session_state.cached_sma = round(df_h['c'].astype(float).tail(10).mean(), 2)
                
                # Update Pivots from latest daily high/low
                high, low = float(res['data']['high']), float(res['data']['low'])
                piv = round((high + low + pc) / 3, 2)
                st.session_state.cached_pivot = piv
                st.session_state.cached_r1 = round((2 * piv) - low, 2)
                st.session_state.cached_s1 = round((2 * piv) - high, 2)
                
                st.session_state.last_hist_update = current_time

        sma = st.session_state.cached_sma
        pivot = st.session_state.cached_pivot
        r1 = st.session_state.cached_r1
        s1 = st.session_state.cached_s1

        # 3. SNIPER LOGIC: DEEP OI & ORDERBOOK (Fast Fetch)
        ce_oi_chg = pe_oi_chg = ce_bid = ce_ask = pe_bid = pe_ask = 0
        tokens_to_fetch = []
        token_map = {}
        
        for i in range(-2, 3):
            strike = atm + (i * step)
            for t in ["CE", "PE"]:
                sym = f"{index}{expiry}{strike}{t}"
                row = df[df['symbol'] == sym]
                if not row.empty:
                    tk = str(row.iloc[0]['token'])
                    tokens_to_fetch.append(tk)
                    token_map[tk] = {"type": t, "strike": strike}

        # Handle API Data carefully
        if tokens_to_fetch:
            m_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            if m_data and m_data.get('status'):
                for item in m_data['data']['fetched']:
                    m = token_map.get(item['symbolToken'])
                    if not m: continue
                    
                    curr_oi = float(item.get('opnInterest', 0))
                    prev_oi = st.session_state.oi_history.get(item['symbolToken'], curr_oi)
                    oi_chg = curr_oi - prev_oi
                    st.session_state.oi_history[item['symbolToken']] = curr_oi
                    
                    b = float(item.get('totalBuyQty', 0))
                    a = float(item.get('totalSellQty', 0))
                    if b == 0 and 'depth' in item and 'buy' in item['depth']: 
                        b = sum([float(x.get('quantity', 0)) for x in item['depth']['buy']])
                    if a == 0 and 'depth' in item and 'sell' in item['depth']: 
                        a = sum([float(x.get('quantity', 0)) for x in item['depth']['sell']])

                    if m['type'] == "CE": ce_oi_chg += oi_chg; ce_ask += a
                    else: pe_oi_chg += oi_chg; pe_bid += b

        # --- UI DISPLAY: DUAL COLUMNS ---
        st.title(f"🏹 {index} HYBRID V81 | Spot: ₹{spot}")
        col_w, col_s = st.columns(2)

        with col_w:
            st.subheader("⚔️ Warrior: Price Levels")
            st.metric("SMA 10", sma, delta=round(spot-sma, 2))
            st.write(f"**Pivot:** {pivot} | **R1:** {r1} | **S1:** {s1}")
            warrior_conf = sum([spot > sma, spot > pc, spot > pivot])
            st.progress(warrior_conf/3 if sma > 0 else 0.0)

        with col_s:
            st.subheader("🎯 Sniper: Data Sentiment")
            pcr_local = round(pe_oi_chg/ce_oi_chg, 2) if ce_oi_chg != 0 else 1.0
            st.metric("Net OI Change", int(pe_oi_chg - ce_oi_chg), delta=f"PCR: {pcr_local}")
            st.write(f"**Orderbook:** Bids {int(pe_bid):,} | Asks {int(ce_ask):,}")
            sniper_conf = sum([pe_oi_chg > ce_oi_chg, pe_bid > ce_ask])
            st.progress(sniper_conf/2 if (pe_oi_chg != 0 or ce_oi_chg !=0) else 0.0)

        # --- MASTER EXECUTION ---
        st.divider()
        is_bull = (warrior_conf >= 2 and sniper_conf >= 1 and spot > pivot)
        is_bear = (warrior_conf <= 1 and sniper_conf <= 0 and spot < pivot)

        if is_bull: st.success("🚀 DUAL CONFIRMATION: BUY CALL")
        elif is_bear: st.error("🩸 DUAL CONFIRMATION: BUY PUT")
        else: st.info("📡 SCANNING: Waiting for Logic Sync...")

        # Increased sleep to 3 seconds for safe Angel API Limits
        time.sleep(3)
        st.rerun()

    except Exception as e:
        # Graceful Error Handling
        st.warning(f"⚠️ Safe Reloading due to API Limit... ({e})")
        time.sleep(4)
        st.rerun()
