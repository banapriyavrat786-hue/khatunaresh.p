import streamlit as st
from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
import time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V77 | Pivot Edition", layout="wide")

# --- CSS STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #00ffcc; }
    .stProgress > div > div > div > div { background-color: #10b981; }
    </style>
    """, unsafe_allow_html=True)

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history']:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ['price_history', 'trade_history'] else None

def get_time():
    try: return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except: return int(time.time())

# -- SIDEBAR CONTROLS --
st.sidebar.title("🚀 Sniper V77 Pro")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED", value=True)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade", value=False)

st.sidebar.divider()
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 16APR26)", "16APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 30, 1)

# --- NEW: PIVOT SETTINGS ---
with st.sidebar.expander("📐 Daily Pivot Data (Prev Day)", expanded=True):
    st.caption("Update these daily for accurate Pivots")
    prev_h = st.number_input("Prev High", value=24200.0)
    prev_l = st.number_input("Prev Low", value=24000.0)
    prev_c = st.number_input("Prev Close", value=24100.0)

st.sidebar.subheader("🎯 Trade Setup")
tgt = st.sidebar.number_input("Target Pts", 40.0, step=5.0)
sl = st.sidebar.number_input("SL Pts", 20.0, step=5.0)
min_vix = st.sidebar.number_input("Min VIX", value=11.5)
mpin = st.sidebar.text_input("MPIN", type="password")

# --- SECURE LOGIN LOGIC ---
if st.sidebar.button("🔑 Connect Securely"):
    try:
        raw_data = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=15).json()
        df_temp = pd.DataFrame(raw_data)
        st.session_state.token_df = df_temp[df_temp['exch_seg'] == "NFO"]
        
        otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).at(get_time())
        obj = SmartConnect(api_key=API_KEY)
        login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        
        if login.get('status'):
            st.session_state.connected, st.session_state.obj = True, obj
            st.sidebar.success("✅ Connected & Ready!")
        else:
            st.sidebar.error("❌ Invalid Login Credentials")
    except Exception as e:
        st.sidebar.error(f"❌ Network/API Error: {e}")

# -- MAIN TRADING ENGINE --
if st.session_state.connected and live_feed:
    obj = st.session_state.obj
    df = st.session_state.token_df
    
    step = 50 if index == "NIFTY" else 100
    qty = (50 if index == "NIFTY" else 15) * lots

    try:
        # 1. SPOT & VIX FETCH
        idx_tok = "26000" if index == "NIFTY" else "26009"
        res = obj.ltpData("NSE", index, idx_tok)
        vix_res = obj.ltpData("NSE", "INDIA VIX", "26017")
        
        if res and res.get('status'):
            spot = float(res['data']['ltp'])
            vix = float(vix_res['data']['ltp']) if (vix_res and vix_res.get('status')) else 12.0
            atm = int(round(spot / step) * step)

            st.session_state.price_history.append(spot)
            if len(st.session_state.price_history) > 30: st.session_state.price_history.pop(0)
            sma = sum(st.session_state.price_history) / len(st.session_state.price_history)
            price_trend = "Rising" if spot > sma else "Falling"

            # --- CALCULATE PIVOTS ---
            pivot = (prev_h + prev_l + prev_c) / 3
            r1 = (2 * pivot) - prev_l
            s1 = (2 * pivot) - prev_h
            r2 = pivot + (prev_h - prev_l)
            s2 = pivot - (prev_h - prev_l)

            # 2. TOKEN GENERATOR
            ce_tokens, pe_tokens = [], []
            token_map = {}
            for i in range(-5, 6):
                strike = atm + (i * step)
                
                ce_sym = f"{index}{expiry}{strike}CE"
                ce_row = df[df['symbol'] == ce_sym]
                if not ce_row.empty:
                    tk = str(ce_row.iloc[0]['token'])
                    ce_tokens.append(tk); token_map[tk] = {"type": "CE", "strike": strike, "sym": ce_sym}
                
                pe_sym = f"{index}{expiry}{strike}PE"
                pe_row = df[df['symbol'] == pe_sym]
                if not pe_row.empty:
                    tk = str(pe_row.iloc[0]['token'])
                    pe_tokens.append(tk); token_map[tk] = {"type": "PE", "strike": strike, "sym": pe_sym}

            if not ce_tokens and not pe_tokens:
                st.error(f"⚠️ Expiry '{expiry}' Not Found.")
                st.stop()

            # 3. GET FULL DEPTH & ORDERBOOK EXTRACTION
            raw_data_list = []
            if ce_tokens:
                ce_data = obj.getMarketData("FULL", {"NFO": ce_tokens})
                if ce_data and ce_data.get('status'): raw_data_list.extend(ce_data['data']['fetched'])
            time.sleep(0.1)
            if pe_tokens:
                pe_data = obj.getMarketData("FULL", {"NFO": pe_tokens})
                if pe_data and pe_data.get('status'): raw_data_list.extend(pe_data['data']['fetched'])

            master_list = []
            ce_oi = pe_oi = ce_bid = ce_ask = pe_bid = pe_ask = 0
            atm_ce_ltp = atm_pe_ltp = 0

            for item in raw_data_list:
                m = token_map.get(item['symbolToken'])
                if not m: continue
                
                b = float(item.get('totalBuyQty', 0))
                a = float(item.get('totalSellQty', 0))
                
                # Deep Orderbook Extraction (Fix for Zero Data)
                if b == 0 and 'depth' in item and 'buy' in item['depth']:
                    b = sum([float(order.get('quantity', 0)) for order in item['depth']['buy']])
                if a == 0 and 'depth' in item and 'sell' in item['depth']:
                    a = sum([float(order.get('quantity', 0)) for order in item['depth']['sell']])

                o = float(item.get('opnInterest', 0))
                ltp = float(item.get('ltp', 0))
                
                if m['type'] == "CE": 
                    ce_oi += o; ce_bid += b; ce_ask += a
                    if m['strike'] == atm: atm_ce_ltp = ltp
                else: 
                    pe_oi += o; pe_bid += b; pe_ask += a
                    if m['strike'] == atm: atm_pe_ltp = ltp
                    
                master_list.append({"Strike": m['strike'], "Type": m['type'], "LTP": ltp, "Bids": b, "Asks": a, "OI": o})

            df_m = pd.DataFrame(master_list)
            
            # --- CALCULATE INSTITUTIONAL S/R ---
            pcr = round(pe_oi/ce_oi, 2) if ce_oi > 0 else 1.0
            inst_resistance, inst_support = 0, 0
            if not df_m.empty:
                ce_data = df_m[df_m['Type'] == 'CE']
                if not ce_data.empty: inst_resistance = ce_data.loc[ce_data['OI'].idxmax()]['Strike']
                pe_data = df_m[df_m['Type'] == 'PE']
                if not pe_data.empty: inst_support = pe_data.loc[pe_data['OI'].idxmax()]['Strike']

            # --- UI: MARKET DASHBOARD ---
            st.title(f"🏹 {index} COMMAND CENTER V77")
            st.subheader(f"📊 Deep Orderbook + Pivot Engine | Spot: ₹{spot}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("India VIX", vix, delta="Safe" if vix >= min_vix else "Low Vol", delta_color="normal" if vix >= min_vix else "inverse")
            c2.metric("Global PCR", pcr, delta="Bullish" if pcr > 1 else "Bearish")
            c3.metric("Trend (SMA 30)", round(sma, 2), delta="Rising" if spot > sma else "Falling")
            c4.metric("ATM CE/PE LTP", f"{atm_ce_ltp} / {atm_pe_ltp}")

            st.divider()

            # --- UI: PIVOT ZONES (NEW) ---
            st.subheader("📐 Price Action Zones (Pivot Levels)")
            p1, p2, p3, p4, p5 = st.columns(5)
            p1.metric("Support 2 (S2)", round(s2, 1))
            p2.metric("Support 1 (S1)", round(s1, 1))
            p3.metric("Main Pivot (P)", round(pivot, 1), delta="Spot is Above" if spot > pivot else "Spot is Below", delta_color="normal" if spot > pivot else "inverse")
            p4.metric("Resistance 1 (R1)", round(r1, 1))
            p5.metric("Resistance 2 (R2)", round(r2, 1))

            st.divider()
            
            # --- UI: S/R METRICS ---
            s1, s2 = st.columns(2)
            s1.metric("🛡️ Inst. Support (Max PE OI)", inst_support, delta="Holding" if spot > inst_support else "Breached", delta_color="normal" if spot > inst_support else "inverse")
            s2.metric("🏰 Inst. Resistance (Max CE OI)", inst_resistance, delta="Holding" if spot < inst_resistance else "Breached", delta_color="inverse" if spot > inst_resistance else "normal")
            
            st.divider()

            # --- UI: BATTLEGROUND ---
            t1, t2 = st.columns(2)
            def format_table(df_subset, r_type):
                df_clean = df_subset.copy()
                if r_type == "CE": df_clean['Strike'] = df_clean['Strike'].apply(lambda x: f"🏰 {x}" if x == inst_resistance else str(x))
                else: df_clean['Strike'] = df_clean['Strike'].apply(lambda x: f"🛡️ {x}" if x == inst_support else str(x))
                df_clean['LTP'] = df_clean['LTP'].apply(lambda x: f"₹ {x:.1f}")
                df_clean['Bids'] = df_clean['Bids'].apply(lambda x: f"{int(x):,}")
                df_clean['Asks'] = df_clean['Asks'].apply(lambda x: f"{int(x):,}")
                df_clean['OI'] = df_clean['OI'].apply(lambda x: f"{int(x):,}")
                return df_clean

            if not df_m.empty:
                with t1:
                    st.subheader("🔴 Call Zone (Supply)")
                    ce_df = df_m[df_m['Type']=="CE"].sort_values("Strike")
                    if not ce_df.empty: st.dataframe(format_table(ce_df, "CE"), hide_index=True, use_container_width=True)
                with t2:
                    st.subheader("🟢 Put Zone (Demand)")
                    pe_df = df_m[df_m['Type']=="PE"].sort_values("Strike", ascending=False)
                    if not pe_df.empty: st.dataframe(format_table(pe_df, "PE"), hide_index=True, use_container_width=True)

            # --- UI: EXECUTION LOGIC (Updated with Pivots) ---
            st.divider()
            st.subheader("📋 Market Strength Checklist (Orderbook + Pivot Verified)")
            
            chk_ce = {
                "Spot > SMA (Bull Trend)": spot > sma,
                "Spot > Pivot (Price Action Bullish)": spot > pivot, # NEW PIVOT LOGIC
                "PCR > 1.0 (Put Writers Active)": pcr > 1.0,
                "Heavy Demand (PE Bids > CE Asks)": pe_bid > ce_ask,
                "CE Premium Expanding": atm_ce_ltp > atm_pe_ltp,
                "OI Support Holds": spot > inst_support
            }
            chk_pe = {
                "Spot < SMA (Bear Trend)": spot < sma,
                "Spot < Pivot (Price Action Bearish)": spot < pivot, # NEW PIVOT LOGIC
                "PCR < 1.0 (Call Writers Active)": pcr < 1.0,
                "Heavy Supply (CE Asks > PE Bids)": ce_ask > pe_bid,
                "PE Premium Expanding": atm_pe_ltp > atm_ce_ltp,
                "OI Resistance Holds": spot < inst_resistance
            }

            st.caption(f"⚔️ **Live Battle:** Total Bids (PE Support): {int(pe_bid):,}  |  Total Asks (CE Resistance): {int(ce_ask):,}")

            l1, l2 = st.columns(2)
            with l1:
                for txt, val in chk_ce.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                ce_score = sum(chk_ce.values())
                ce_conf = (ce_score / len(chk_ce)) * 100
                st.metric("CALL Confidence", f"{int(ce_conf)}%")
                st.progress(ce_score/len(chk_ce))
            with l2:
                for txt, val in chk_pe.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                pe_score = sum(chk_pe.values())
                pe_conf = (pe_score / len(chk_pe)) * 100
                st.metric("PUT Confidence", f"{int(pe_conf)}%")
                st.progress(pe_score/len(chk_pe))

            # --- ACTIVE TRADE TRACKER ---
            st.divider()
            st.subheader("⏱️ Active Trade Status")
            
            if st.session_state.active_trade is None:
                st.info("No active trades currently. Monitoring conditions...")
                if auto_trade and vix >= min_vix:
                    # Require strong confidence (approx 83% or 5 out of 6 ticks)
                    if ce_conf > 80 and atm_ce_ltp > 0:
                        st.success("🚀 CRITERIA MET: AUTO-BUYING CALL")
                        st.session_state.active_trade = {"type": "CE", "entry": spot, "target": spot+tgt, "sl": spot-sl, "time": datetime.now().strftime("%H:%M:%S"), "conf": int(ce_conf)}
                    elif pe_conf > 80 and atm_pe_ltp > 0:
                        st.error("🩸 CRITERIA MET: AUTO-BUYING PUT")
                        st.session_state.active_trade = {"type": "PE", "entry": spot, "target": spot-tgt, "sl": spot+sl, "time": datetime.now().strftime("%H:%M:%S"), "conf": int(pe_conf)}
            else:
                t = st.session_state.active_trade
                pnl = round(spot - t['entry'] if t['type']=="CE" else t['entry'] - spot, 2)
                
                st.warning(f"⚠️ **TRADE RUNNING**")
                tr1, tr2, tr3, tr4, tr5 = st.columns(5)
                tr1.metric("Type", t['type'])
                tr2.metric("Entry Time", t['time'])
                tr3.metric("Entry Spot", f"₹{t['entry']}")
                tr4.metric("Current Spot", f"₹{spot}")
                tr5.metric("Live P&L (Pts)", pnl, delta=pnl)
                
                st.write(f"**Safety/Confidence at Entry:** {t.get('conf', 0)}%")
                st.write(f"**Targets:** Exit expected around **₹{t['target']}** | Stoploss around **₹{t['sl']}**")
                
                is_tgt = spot >= t['target'] if t['type']=="CE" else spot <= t['target']
                is_sl = spot <= t['sl'] if t['type']=="CE" else spot >= t['sl']
                
                if is_tgt or is_sl:
                    res_status = "✅ TARGET HIT" if is_tgt else "❌ SL HIT"
                    st.session_state.trade_history.append({"Time In": t['time'], "Time Out": datetime.now().strftime("%H:%M:%S"), "Type": t['type'], "Entry": t['entry'], "Exit": spot, "PnL": pnl, "Result": res_status})
                    st.session_state.active_trade = None
                    st.success(f"Trade Closed Automatically: {res_status}")
                    time.sleep(2)
                    st.rerun()

                if st.button("🚨 MANUAL EXIT NOW", use_container_width=True):
                    st.session_state.trade_history.append({"Time In": t['time'], "Time Out": datetime.now().strftime("%H:%M:%S"), "Type": t['type'], "Entry": t['entry'], "Exit": spot, "PnL": pnl, "Result": "Manual Exit"})
                    st.session_state.active_trade = None
                    st.rerun()

            # --- LEDGER ---
            if st.session_state.trade_history:
                st.divider()
                st.subheader("📚 Detailed Trade Ledger")
                st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

            time.sleep(2)
            st.rerun()

    except Exception as e:
        st.warning(f"⚠️ System Syncing... Loading Data ({e})")
        time.sleep(2)
        st.rerun()
else:
    if not st.session_state.connected:
        st.info("🔌 System Offline. Enter MPIN and Click Connect.")
