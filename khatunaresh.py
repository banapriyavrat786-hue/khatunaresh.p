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

st.set_page_config(page_title="GRK Sniper V74 | Adaptive", layout="wide")

# --- CSS STYLING ---
st.markdown("""
    <style>
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #00ffcc; }
    .stProgress > div > div > div > div { background-color: #10b981; }
    </style>
    """, unsafe_allow_html=True)

# -- SESSION STATE --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history']:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ['price_history', 'trade_history'] else None

def get_time():
    try: return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except: return int(time.time())

# -- SIDEBAR CONTROLS --
st.sidebar.title("🚀 Sniper V74")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED", value=True)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade", value=False)

st.sidebar.divider()
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 16APR26)", "16APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 30, 1)

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

            # 2. TOKEN GENERATOR (REDUCED TO ±5 STRIKES FOR API SAFETY)
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
                st.error(f"⚠️ Expiry '{expiry}' Data Not Found.")
                st.stop()

            # 3. GET FULL DEPTH
            raw_data_list = []
            if ce_tokens:
                ce_data = obj.getMarketData("FULL", {"NFO": ce_tokens})
                if ce_data and ce_data.get('status'): raw_data_list.extend(ce_data['data']['fetched'])
            
            time.sleep(0.1)
            
            if pe_tokens:
                pe_data = obj.getMarketData("FULL", {"NFO": pe_tokens})
                if pe_data and pe_data.get('status'): raw_data_list.extend(pe_data['data']['fetched'])

            master_list = []
            ce_oi = pe_oi = ce_bid = ce_ask = pe_bid = pe_ask = ce_vol = pe_vol = 0
            atm_ce_ltp = atm_pe_ltp = 0

            for item in raw_data_list:
                m = token_map.get(item['symbolToken'])
                if not m: continue
                
                b = float(item.get('totalBuyQty', 0))
                a = float(item.get('totalSellQty', 0))
                o = float(item.get('opnInterest', 0))
                ltp = float(item.get('ltp', 0))
                v = float(item.get('volume', item.get('tradeVolume', 0))) # Added Volume Backup
                
                if m['type'] == "CE": 
                    ce_oi += o; ce_bid += b; ce_ask += a; ce_vol += v
                    if m['strike'] == atm: atm_ce_ltp = ltp
                else: 
                    pe_oi += o; pe_bid += b; pe_ask += a; pe_vol += v
                    if m['strike'] == atm: atm_pe_ltp = ltp
                    
                master_list.append({"Strike": m['strike'], "Type": m['type'], "LTP": ltp, "Bids": b, "Asks": a, "OI": o, "Volume": v})

            df_m = pd.DataFrame(master_list)
            
            # --- CALCULATE S/R ---
            pcr = round(pe_oi/ce_oi, 2) if ce_oi > 0 else 1.0
            inst_resistance, inst_support = 0, 0
            
            if not df_m.empty:
                ce_data = df_m[df_m['Type'] == 'CE']
                if not ce_data.empty: inst_resistance = ce_data.loc[ce_data['OI'].idxmax()]['Strike']
                pe_data = df_m[df_m['Type'] == 'PE']
                if not pe_data.empty: inst_support = pe_data.loc[pe_data['OI'].idxmax()]['Strike']

            # --- UI: MARKET DASHBOARD ---
            st.title(f"🏹 {index} COMMAND CENTER V74")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LIVE SPOT", f"₹{spot}")
            c2.metric("India VIX", vix, delta="Safe" if vix >= min_vix else "Low Vol", delta_color="normal" if vix >= min_vix else "inverse")
            c3.metric("Global PCR", pcr, delta="Bullish" if pcr > 1 else "Bearish")
            c4.metric("ATM CE/PE LTP", f"{atm_ce_ltp} / {atm_pe_ltp}")

            st.divider()
            
            # --- UI: S/R METRICS ---
            s1, s2 = st.columns(2)
            s1.metric("🛡️ Institutional Support (PE OI)", inst_support, delta="Holding" if spot > inst_support else "Breached", delta_color="normal" if spot > inst_support else "inverse")
            s2.metric("🏰 Institutional Resistance (CE OI)", inst_resistance, delta="Holding" if spot < inst_resistance else "Breached", delta_color="inverse" if spot > inst_resistance else "normal")
            
            st.divider()

            # --- UI: BATTLEGROUND TABLE ---
            t1, t2 = st.columns(2)
            
            def format_table(df_subset, r_type):
                df_clean = df_subset.copy()
                if r_type == "CE":
                    df_clean['Strike'] = df_clean['Strike'].apply(lambda x: f"🏰 {x}" if x == inst_resistance else str(x))
                else:
                    df_clean['Strike'] = df_clean['Strike'].apply(lambda x: f"🛡️ {x}" if x == inst_support else str(x))
                
                df_clean['LTP'] = df_clean['LTP'].apply(lambda x: f"₹ {x:.1f}")
                df_clean['Bids'] = df_clean['Bids'].apply(lambda x: f"{int(x):,}" if x > 0 else "-")
                df_clean['Asks'] = df_clean['Asks'].apply(lambda x: f"{int(x):,}" if x > 0 else "-")
                df_clean['OI'] = df_clean['OI'].apply(lambda x: f"{int(x):,}")
                df_clean['Volume'] = df_clean['Volume'].apply(lambda x: f"{int(x):,}")
                return df_clean

            if not df_m.empty:
                with t1:
                    st.subheader("🔴 Call Zone (Supply)")
                    ce_raw = df_m[(df_m['Type']=="CE")].sort_values("Strike")
                    if not ce_raw.empty: st.dataframe(format_table(ce_raw, "CE"), hide_index=True, use_container_width=True)
                    
                with t2:
                    st.subheader("🟢 Put Zone (Demand)")
                    pe_raw = df_m[(df_m['Type']=="PE")].sort_values("Strike", ascending=False)
                    if not pe_raw.empty: st.dataframe(format_table(pe_raw, "PE"), hide_index=True, use_container_width=True)

            # --- ADAPTIVE EXECUTION LOGIC (Zero-Data Protected) ---
            st.divider()
            st.subheader("📋 Adaptive Logic Checklist")
            
            # Agar Bids/Asks 0 hain, toh logic Volume aur OI par shift ho jayega
            orderbook_active = (pe_bid + ce_ask) > 0
            
            if orderbook_active:
                bull_pressure = pe_bid > ce_ask
                bear_pressure = ce_ask > pe_bid
                pressure_label = "Bids > Asks (Heavy Demand)"
            else:
                bull_pressure = pe_vol > ce_vol
                bear_pressure = ce_vol > pe_vol
                pressure_label = "PE Volume > CE Volume (Fallback Demand)"

            chk_ce = {
                "Spot > SMA (Bull Trend)": spot > sma,
                "PCR > 1.0 (Put Writers Active)": pcr > 1.0,
                pressure_label: bull_pressure,
                "CE Premium Expanding": atm_ce_ltp > atm_pe_ltp,
                "Support Holds": spot > inst_support
            }
            
            chk_pe = {
                "Spot < SMA (Bear Trend)": spot < sma,
                "PCR < 1.0 (Call Writers Active)": pcr < 1.0,
                pressure_label.replace("Demand", "Supply").replace("PE", "CE").replace("Bids", "Asks"): bear_pressure,
                "PE Premium Expanding": atm_pe_ltp > atm_ce_ltp,
                "Resistance Holds": spot < inst_resistance
            }

            if orderbook_active:
                st.caption(f"⚔️ **Live Battle:** PE Bids: {int(pe_bid):,}  |  CE Asks: {int(ce_ask):,}")
            else:
                st.caption(f"⚠️ API Orderbook Blocked. Using Volume Fallback | PE Vol: {int(pe_vol):,} | CE Vol: {int(ce_vol):,}")

            l1, l2 = st.columns(2)
            with l1:
                for txt, val in chk_ce.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                ce_score = sum(chk_ce.values())
                ce_conf = (ce_score / len(chk_ce)) * 100
                st.progress(ce_score/len(chk_ce))
                st.write(f"**CALL Confidence: {int(ce_conf)}%**")
            with l2:
                for txt, val in chk_pe.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                pe_score = sum(chk_pe.values())
                pe_conf = (pe_score / len(chk_pe)) * 100
                st.progress(pe_score/len(chk_pe))
                st.write(f"**PUT Confidence: {int(pe_conf)}%**")

            # --- ACTIVE TRADE TRACKER ---
            st.divider()
            st.subheader("⏱️ Active Trade Status")
            
            if st.session_state.active_trade is None:
                st.info("No active trades. Monitoring conditions...")
                if auto_trade and vix >= min_vix:
                    if ce_conf >= 80 and atm_ce_ltp > 0:
                        st.session_state.active_trade = {"type": "CE", "entry": spot, "target": spot+tgt, "sl": spot-sl, "time": datetime.now().strftime("%H:%M:%S")}
                    elif pe_conf >= 80 and atm_pe_ltp > 0:
                        st.session_state.active_trade = {"type": "PE", "entry": spot, "target": spot-tgt, "sl": spot+sl, "time": datetime.now().strftime("%H:%M:%S")}
            else:
                t = st.session_state.active_trade
                pnl = round(spot - t['entry'] if t['type']=="CE" else t['entry'] - spot, 2)
                
                tr1, tr2, tr3, tr4, tr5 = st.columns(5)
                tr1.metric("Type", t['type'])
                tr2.metric("Entry Time", t['time'])
                tr3.metric("Entry Spot", f"₹{t['entry']:.2f}")
                tr4.metric("Live Spot", f"₹{spot:.2f}")
                tr5.metric("Live P&L", f"{pnl:.2f} Pts", delta=pnl)
                
                is_tgt = spot >= t['target'] if t['type']=="CE" else spot <= t['target']
                is_sl = spot <= t['sl'] if t['type']=="CE" else spot >= t['sl']
                
                if is_tgt or is_sl or st.button("🚨 MANUAL EXIT NOW"):
                    res = "TARGET" if is_tgt else ("SL" if is_sl else "MANUAL")
                    st.session_state.trade_history.append({"Time In": t['time'], "Time Out": datetime.now().strftime("%H:%M:%S"), "Type": t['type'], "Entry": f"₹{t['entry']:.2f}", "Exit": f"₹{spot:.2f}", "PnL": pnl, "Result": res})
                    st.session_state.active_trade = None
                    st.rerun()

            if st.session_state.trade_history:
                st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

            time.sleep(2)
            st.
