import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V69 | Flawless", layout="wide")

# --- UI & CSS ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
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

@st.cache_data(ttl=3600)
def load_tokens():
    try:
        res = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=30)
        return pd.DataFrame(res.json()[df['exch_seg'] == "NFO"])
    except: return None

# -- SIDEBAR --
st.sidebar.title("🚀 Flawless Sniper")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED", value=True)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade", value=False)

st.sidebar.divider()
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 16APR26)", "16APR26").upper()
# Max lot safety (Nifty 1800 qty limit safe side)
lots = st.sidebar.number_input("Lots", 1, 30, 1) 

st.sidebar.subheader("🎯 Trade Setup")
tgt = st.sidebar.number_input("Target Pts", 40.0, step=5.0)
sl = st.sidebar.number_input("SL Pts", 20.0, step=5.0)
min_vix = st.sidebar.number_input("Min VIX", value=11.5)

mpin = st.sidebar.text_input("MPIN", type="password")

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
            st.sidebar.error("❌ Invalid Login")
    except Exception as e:
        st.sidebar.error(f"❌ Connection Error: API/Network issue.")

# -- MAIN ENGINE --
if st.session_state.connected and live_feed:
    obj, df = st.session_state.obj, st.session_state.token_df
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

            # 2. TOKEN GENERATOR (SAFE LIMIT: 42 TOKENS)
            tokens_to_fetch = []
            token_map = {}
            for i in range(-10, 11):
                for sfx in ["CE", "PE"]:
                    sym = f"{index}{expiry}{atm+(i*step)}{sfx}"
                    t_rows = df[df['symbol'] == sym]
                    if not t_rows.empty:
                        tk = str(t_rows.iloc[0]['token'])
                        tokens_to_fetch.append(tk)
                        token_map[tk] = {"type": sfx, "strike": atm+(i*step), "sym": sym}

            if not tokens_to_fetch:
                st.error("⚠️ Expiry Match Nahi Hui. Kripya Expiry Format Check Karein (e.g. 16APR26)")
                st.stop()

            # 3. GET FULL DEPTH
            full_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            master_list = []
            ce_oi = pe_oi = ce_bid = ce_ask = pe_bid = pe_ask = 0
            atm_ce_ltp = atm_pe_ltp = 0

            if full_data and full_data.get('status') and 'fetched' in full_data['data']:
                for item in full_data['data']['fetched']:
                    m = token_map.get(item['symbolToken'])
                    if not m: continue
                    
                    b = float(item.get('totalBuyQty', 0))
                    a = float(item.get('totalSellQty', 0))
                    o = float(item.get('opnInterest', 0))
                    ltp = float(item.get('ltp', 0))
                    
                    if m['type'] == "CE": 
                        ce_oi += o; ce_bid += b; ce_ask += a
                        if m['strike'] == atm: atm_ce_ltp = ltp
                    else: 
                        pe_oi += o; pe_bid += b; pe_ask += a
                        if m['strike'] == atm: atm_pe_ltp = ltp
                        
                    master_list.append({"Strike": m['strike'], "Type": m['type'], "LTP": ltp, "Bids": b, "Asks": a, "OI": o})

            pcr = round(pe_oi/ce_oi, 2) if ce_oi > 0 else 1.0

            # --- UI: MARKET DASHBOARD ---
            st.title(f"🏹 {index} FLAWLESS ENGINE V69")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LIVE SPOT", f"₹{spot}")
            c2.metric("India VIX", vix, delta="Safe" if vix >= min_vix else "Low Vol", delta_color="normal" if vix >= min_vix else "inverse")
            c3.metric("GLOBAL PCR", pcr, delta="Bullish" if pcr > 1 else "Bearish")
            c4.metric("ATM Momentum (CE/PE)", f"{atm_ce_ltp} / {atm_pe_ltp}")

            st.divider()

            # --- UI: CLEAN BATTLEGROUND ---
            t1, t2 = st.columns(2)
            df_m = pd.DataFrame(master_list)
            
            # Filtering Top 10 Relevant Strikes
            if not df_m.empty:
                with t1:
                    st.subheader("🔴 Call Sellers (Resistance Zone)")
                    ce_df = df_m[(df_m['Type']=="CE") & (df_m['Strike'] >= atm - (step*2))].sort_values("Strike").head(10)
                    st.dataframe(ce_df, hide_index=True, use_container_width=True)
                with t2:
                    st.subheader("🟢 Put Buyers (Support Zone)")
                    pe_df = df_m[(df_m['Type']=="PE") & (df_m['Strike'] <= atm + (step*2))].sort_values("Strike", ascending=False).head(10)
                    st.dataframe(pe_df, hide_index=True, use_container_width=True)

            # --- UI: EXECUTION LOGIC ---
            st.divider()
            st.subheader("📋 Execution Setup")
            
            chk_ce = {
                "Spot is above SMA": spot > sma,
                "PCR > 1.0 (Put Writers active)": pcr > 1.0,
                "Strong Support (PE Bids > CE Asks)": pe_bid > ce_ask,
                "Premium Expanding (CE > PE)": atm_ce_ltp > atm_pe_ltp
            }
            chk_pe = {
                "Spot is below SMA": spot < sma,
                "PCR < 1.0 (Call Writers active)": pcr < 1.0,
                "Strong Resistance (CE Asks > PE Bids)": ce_ask > pe_bid,
                "Premium Expanding (PE > CE)": atm_pe_ltp > atm_ce_ltp
            }

            l1, l2 = st.columns(2)
            with l1:
                for txt, val in chk_ce.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                ce_score = sum(chk_ce.values())
                st.progress(ce_score/4)
            with l2:
                for txt, val in chk_pe.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                pe_score = sum(chk_pe.values())
                st.progress(pe_score/4)

            # --- AUTO TRADE & ORDER MANAGEMENT ---
            if st.session_state.active_trade is None:
                if auto_trade and vix >= min_vix:
                    if ce_score == 4 and atm_ce_ltp > 0:
                        st.success("🚀 CRITERIA MET: AUTO-BUYING CALL")
                        st.session_state.active_trade = {"type": "CE", "entry": spot, "target": spot+tgt, "sl": spot-sl}
                    elif pe_score == 4 and atm_pe_ltp > 0:
                        st.error("🩸 CRITERIA MET: AUTO-BUYING PUT")
                        st.session_state.active_trade = {"type": "PE", "entry": spot, "target": spot-tgt, "sl": spot+sl}
            else:
                t = st.session_state.active_trade
                pnl = round(spot - t['entry'] if t['type']=="CE" else t['entry'] - spot, 2)
                
                st.warning(f"⚠️ ACTIVE TRADE: {t['type']} | Spot Entry: {t['entry']} | Live PnL: {pnl} Pts")
                
                # Check Targets/SL
                is_tgt = spot >= t['target'] if t['type']=="CE" else spot <= t['target']
                is_sl = spot <= t['sl'] if t['type']=="CE" else spot >= t['sl']
                
                if is_tgt or is_sl:
                    res_status = "✅ TARGET HIT" if is_tgt else "❌ SL HIT"
                    st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Type": t['type'], "Entry": t['entry'], "Exit": spot, "PnL": pnl, "Result": res_status})
                    st.session_state.active_trade = None
                    st.success(f"Trade Closed: {res_status}")
                    time.sleep(2)
                    st.rerun()

                if st.button("🚨 EXIT NOW"):
                    st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Type": t['type'], "Entry": t['entry'], "Exit": spot, "PnL": pnl, "Result": "Manual Exit"})
                    st.session_state.active_trade = None
                    st.rerun()

            # --- TRADE LEDGER ---
            if st.session_state.trade_history:
                st.divider()
                st.subheader("📚 Trade Ledger")
                st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

            time.sleep(2.5)
            st.rerun()

    except Exception as e:
        st.warning("⚠️ Syncing Data Stream... Retrying in 2 seconds.")
        time.sleep(2)
        st.rerun()
