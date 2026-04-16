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

st.set_page_config(page_title="V82 Ultimate Dashboard", layout="wide")

# -- SESSION STATE: ALL VARIABLES --
if 'connected' not in st.session_state:
    st.session_state.update({
        'obj': None, 'connected': False, 'token_df': None, 
        'oi_history': {}, 'last_hist_update': 0, 
        'cached_sma': 0, 'cached_pivot': 0, 'cached_r1': 0, 'cached_s1': 0,
        'active_trade': None, 'trade_log': []
    })

# --- SIDEBAR & LOGIN ---
st.sidebar.title("🚀 V82 Master System")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 23APR26)", "23APR26").upper()
mpin = st.sidebar.text_input("Angel MPIN", type="password")
auto_trade = st.sidebar.checkbox("🤖 Auto-Trade Master", value=False)

if st.sidebar.button("🔑 Connect System"):
    try:
        raw_data = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=10).json()
        st.session_state.token_df = pd.DataFrame(raw_data)[lambda x: x['exch_seg'] == "NFO"]
        
        obj = SmartConnect(api_key=API_KEY)
        otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).now()
        login = obj.generateSession(CLIENT_ID, mpin, otp)
        
        if login.get('status'):
            st.session_state.obj, st.session_state.connected = obj, True
            st.sidebar.success("✅ Connected to Angel One!")
        else: st.sidebar.error("❌ Login Failed")
    except Exception as e: st.sidebar.error(f"Error: {e}")

# --- THE MAIN ENGINE ---
if st.session_state.connected:
    obj, df = st.session_state.obj, st.session_state.token_df
    idx_tok = "26000" if index == "NIFTY" else "26009"
    step = 50 if index == "NIFTY" else 100

    try:
        # 1. FETCH LIVE SPOT PRICE
        res = obj.ltpData("NSE", index, idx_tok)
        spot, pc = float(res['data']['ltp']), float(res['data']['close'])
        high, low = float(res['data']['high']), float(res['data']['low'])
        atm = int(round(spot / step) * step)

        # 2. SMART CACHE (Force fetch on 0 or every 60s)
        current_time = time.time()
        if st.session_state.cached_sma == 0 or (current_time - st.session_state.last_hist_update) > 60:
            hist = obj.getCandleData({"exchange": "NSE", "symboltoken": idx_tok, "interval": "FIVE_MINUTE", 
                                      "fromdate": (datetime.now()-timedelta(days=3)).strftime('%Y-%m-%d %H:%M'),
                                      "todate": datetime.now().strftime('%Y-%m-%d %H:%M')})
            if hist and hist.get('status'):
                df_h = pd.DataFrame(hist['data'], columns=['t','o','h','l','c','v'])
                st.session_state.cached_sma = round(df_h['c'].astype(float).tail(10).mean(), 2)
            
            piv = round((high + low + pc) / 3, 2)
            st.session_state.cached_pivot = piv
            st.session_state.cached_r1 = round((2 * piv) - low, 2)
            st.session_state.cached_s1 = round((2 * piv) - high, 2)
            st.session_state.last_hist_update = current_time

        sma, pivot = st.session_state.cached_sma, st.session_state.cached_pivot
        r1, s1 = st.session_state.cached_r1, st.session_state.cached_s1

        # 3. SNIPER LOGIC: DEEP OI & ORDERBOOK
        ce_oi_chg = pe_oi_chg = ce_bid = ce_ask = pe_bid = pe_ask = 0
        tokens_to_fetch, token_map = [], {}
        for i in range(-2, 3):
            strike = atm + (i * step)
            for t in ["CE", "PE"]:
                sym = f"{index}{expiry}{strike}{t}"
                row = df[df['symbol'] == sym]
                if not row.empty:
                    tk = str(row.iloc[0]['token'])
                    tokens_to_fetch.append(tk); token_map[tk] = {"type": t}

        if tokens_to_fetch:
            m_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            if m_data and m_data.get('status'):
                for item in m_data['data']['fetched']:
                    m = token_map.get(item['symbolToken'])
                    if not m: continue
                    
                    curr_oi = float(item.get('opnInterest', 0))
                    oi_chg = curr_oi - st.session_state.oi_history.get(item['symbolToken'], curr_oi)
                    st.session_state.oi_history[item['symbolToken']] = curr_oi
                    
                    b, a = float(item.get('totalBuyQty', 0)), float(item.get('totalSellQty', 0))
                    if b == 0 and 'depth' in item: b = sum([float(x.get('quantity',0)) for x in item['depth'].get('buy',[])])
                    if a == 0 and 'depth' in item: a = sum([float(x.get('quantity',0)) for x in item['depth'].get('sell',[])])

                    if m['type'] == "CE": ce_oi_chg += oi_chg; ce_ask += a
                    else: pe_oi_chg += oi_chg; pe_bid += b

        # ==========================================
        # UI DESIGN: THE SYSTEMATIC DASHBOARD
        # ==========================================
        st.title(f"🏛️ MASTER DASHBOARD | {index} Spot: ₹{spot}")
        
        # --- TOP LEVEL: SIGNAL BOX ---
        w_bull = spot > sma and spot > pivot
        s_bull = pe_oi_chg > ce_oi_chg and pe_bid > ce_ask
        w_bear = spot < sma and spot < pivot
        s_bear = ce_oi_chg > pe_oi_chg and ce_ask > pe_bid

        if w_bull and s_bull: st.success("🟢 MASTER SIGNAL: DUAL CONFIRMATION (CALL BUY)")
        elif w_bear and s_bear: st.error("🔴 MASTER SIGNAL: DUAL CONFIRMATION (PUT BUY)")
        else: st.warning("🟡 SCANNING: Waiting for Both Logics to Sync...")

        st.divider()

        # --- MIDDLE LEVEL: DUAL LOGIC CHECKLISTS ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.header("⚔️ Warrior: Price Engine")
            st.metric("SMA 10", sma, delta=round(spot-sma, 2))
            st.markdown(f"**Pivot:** `{pivot}` | **R1:** `{r1}` | **S1:** `{s1}`")
            
            st.subheader("📋 Price Checklist")
            st.write(f"{'✅' if spot > sma else '❌'} Spot > SMA 10 (Trend)")
            st.write(f"{'✅' if spot > pivot else '❌'} Spot > Pivot (Momentum)")
            st.write(f"{'✅' if spot > pc else '❌'} Spot > Prev Close (Sentiment)")

        with col2:
            st.header("🎯 Sniper: Data Engine")
            pcr_local = round(pe_oi_chg/ce_oi_chg, 2) if ce_oi_chg > 0 else 1.0
            st.metric("Net OI Change", int(pe_oi_chg - ce_oi_chg), delta=f"PCR: {pcr_local}")
            st.markdown(f"**Bids (Demand):** `{int(pe_bid):,}` | **Asks (Supply):** `{int(ce_ask):,}`")
            
            st.subheader("📋 Institutional Checklist")
            st.write(f"{'✅' if pe_oi_chg > ce_oi_chg else '❌'} PE Writers > CE Writers (Support Built)")
            st.write(f"{'✅' if pe_bid > ce_ask else '❌'} Demand > Supply (Orderbook)")
            st.write(f"{'✅' if pcr_local > 1 else '❌'} Local PCR Bullish")

        st.divider()

        # --- BOTTOM LEVEL: TRADE MANAGEMENT ---
        st.header("💼 Trade Management Terminal")
        
        # Auto-Trade Execution Logic
        if auto_trade and st.session_state.active_trade is None:
            if w_bull and s_bull:
                st.session_state.active_trade = {"Type": "CALL", "Entry": spot, "SL": pivot, "Time": datetime.now().strftime("%H:%M")}
            elif w_bear and s_bear:
                st.session_state.active_trade = {"Type": "PUT", "Entry": spot, "SL": pivot, "Time": datetime.now().strftime("%H:%M")}

        # Live Trade Tracker
        if st.session_state.active_trade:
            t = st.session_state.active_trade
            pnl = round((spot - t['Entry']) if t['Type'] == "CALL" else (t['Entry'] - spot), 2)
            
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.info(f"**Active:** {t['Type']}")
            tc2.metric("Entry Price", f"₹{t['Entry']}")
            tc3.metric("Live P&L", f"{pnl} Pts", delta=pnl)
            tc4.warning(f"Stoploss: ₹{t['SL']}")

            if st.button("🚨 Square Off & Log Trade"):
                st.session_state.trade_log.append({"Time": t['Time'], "Type": t['Type'], "Entry": t['Entry'], "Exit": spot, "PnL": pnl})
                st.session_state.active_trade = None
                st.rerun()
        else:
            st.info("No Active Trades. Scanning market conditions...")

        # Trade Book (Ledger)
        with st.expander("📚 View Trade Book (Ledger)"):
            if st.session_state.trade_log:
                st.dataframe(pd.DataFrame(st.session_state.trade_log), use_container_width=True)
            else:
                st.write("No trades taken yet.")

        time.sleep(3)
        st.rerun()

    except Exception as e:
        st.warning(f"⚠️ Fetching Data/Market Closed... ({e})")
        time.sleep(3)
        st.rerun()
