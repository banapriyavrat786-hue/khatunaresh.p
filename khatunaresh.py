import streamlit as st
from SmartApi import SmartConnect
import pyotp
import pandas as pd
import time
from datetime import datetime, timedelta

# -- CONFIGURATION (Angel One) --
CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="Warrior-Sniper V80 | Full Power", layout="wide")

# -- SESSION STATE: KUCH BHI NAHI BHOOLENGE --
if 'connected' not in st.session_state:
    keys = ['obj', 'connected', 'token_df', 'active_trade', 'trade_history', 'price_history', 'oi_history']
    for k in keys: st.session_state[k] = {} if k == 'oi_history' else ([] if k in ['price_history', 'trade_history'] else None)

# --- SIDEBAR & LOGIN ---
st.sidebar.title("🚀 Warrior-Sniper V80")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 23APR26)", "23APR26").upper()
mpin = st.sidebar.text_input("Angel MPIN", type="password")
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade (Dual Sync)", value=False)

if st.sidebar.button("🔑 Connect Fully"):
    try:
        # Fetching Tokens
        raw_data = pd.DataFrame(requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json").json())
        st.session_state.token_df = raw_data[raw_data['exch_seg'] == "NFO"]
        
        obj = SmartConnect(api_key=API_KEY)
        otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).now()
        login = obj.generateSession(CLIENT_ID, mpin, otp)
        if login.get('status'):
            st.session_state.obj, st.session_state.connected = obj, True
            st.sidebar.success("✅ Dual Engine Online!")
    except Exception as e: st.sidebar.error(f"Error: {e}")

# --- THE MAIN ENGINE ---
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df
    idx_tok = "26000" if index == "NIFTY" else "26009"
    step = 50 if index == "NIFTY" else 100

    try:
        # 1. FETCH BASE DATA (Price & OHLC)
        res = obj.ltpData("NSE", index, idx_tok)
        spot = float(res['data']['ltp'])
        pc, high, low = float(res['data']['close']), float(res['data']['high']), float(res['data']['low'])
        atm = int(round(spot / step) * step)

        # 2. WARRIOR LOGIC: SMA 10 (Price History)
        hist = obj.getCandleData({"exchange": "NSE", "symboltoken": idx_tok, "interval": "FIVE_MINUTE", 
                                  "fromdate": (datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
                                  "todate": datetime.now().strftime('%Y-%m-%d %H:%M')})
        df_h = pd.DataFrame(hist['data'], columns=['t','o','h','l','c','v'])
        sma = round(df_h['c'].astype(float).tail(10).mean(), 2)

        # 3. WARRIOR LOGIC: PIVOTS
        pivot = round((high + low + pc) / 3, 2)
        r1, s1 = round((2 * pivot) - low, 2), round((2 * pivot) - high, 2)

        # 4. SNIPER LOGIC: DEEP OI & ORDERBOOK (±3 Strikes)
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

        m_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
        if m_data['status']:
            for item in m_data['data']['fetched']:
                m = token_map.get(item['symbolToken'])
                curr_oi = float(item.get('opnInterest', 0))
                # OI Change calculation (Sniper Logic)
                prev_oi = st.session_state.oi_history.get(item['symbolToken'], curr_oi)
                oi_chg = curr_oi - prev_oi
                st.session_state.oi_history[item['symbolToken']] = curr_oi
                
                # Deep Depth Check
                b = float(item.get('totalBuyQty', 0))
                a = float(item.get('totalSellQty', 0))
                if b == 0 and 'depth' in item: b = sum([float(x['quantity']) for x in item['depth']['buy']])
                if a == 0 and 'depth' in item: a = sum([float(x['quantity']) for x in item['depth']['sell']])

                if m['type'] == "CE": ce_oi_chg += oi_chg; ce_ask += a
                else: pe_oi_chg += oi_chg; pe_bid += b

        # --- UI DISPLAY: DUAL COLUMNS ---
        st.title(f"🏹 {index} HYBRID V80 | Spot: ₹{spot}")
        col_w, col_s = st.columns(2)

        with col_w:
            st.subheader("⚔️ Warrior: Price Levels")
            st.metric("SMA 10", sma, delta=round(spot-sma, 2))
            st.write(f"**Pivot:** {pivot} | **R1:** {r1} | **S1:** {s1}")
            warrior_conf = sum([spot > sma, spot > pc, spot > pivot])
            st.progress(warrior_conf/3)

        with col_s:
            st.subheader("🎯 Sniper: Data Sentiment")
            pcr_local = round(pe_oi_chg/ce_oi_chg, 2) if ce_oi_chg != 0 else 1.0
            st.metric("Net OI Change", int(pe_oi_chg - ce_oi_chg), delta=f"PCR: {pcr_local}")
            st.write(f"**Orderbook:** Bids {int(pe_bid):,} | Asks {int(ce_ask):,}")
            sniper_conf = sum([pe_oi_chg > ce_oi_chg, pe_bid > ce_ask])
            st.progress(sniper_conf/2)

        # --- MASTER EXECUTION ---
        st.divider()
        is_bull = (warrior_conf >= 2 and sniper_conf >= 1 and spot > pivot)
        is_bear = (warrior_conf <= 1 and sniper_conf <= 0 and spot < pivot)

        if is_bull: st.success("🚀 DUAL CONFIRMATION: BUY CALL")
        elif is_bear: st.error("🩸 DUAL CONFIRMATION: BUY PUT")
        else: st.info("📡 SCANNING: Waiting for Logic Sync...")

        time.sleep(2)
        st.rerun()

    except Exception as e:
        st.toast(f"Syncing Engine... {e}")
        time.sleep(2)
        st.rerun()
