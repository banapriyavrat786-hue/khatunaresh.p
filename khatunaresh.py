import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V24", layout="wide")
st.title("🤖 MKPV Auto-Sniper | Volume & OI Logic")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'price_history' not in st.session_state: st.session_state.price_history = []

def get_internet_time():
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return r.json()['unixtime']
    except: return int(time.time())

@st.cache_data(ttl=3600)
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        res = requests.get(url, timeout=15)
        df = pd.DataFrame(res.json())
        return df[df['exch_seg'] == 'NFO']
    except: return None

# -- SIDEBAR --
st.sidebar.title("⚙️ Robot Controls")
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots", min_value=1, value=1)

st.sidebar.subheader("🎯 Spot Targets (Points)")
tgt_points = st.sidebar.number_input("Target", value=40)
sl_points = st.sidebar.number_input("StopLoss", value=20)
mpin = st.sidebar.text_input("MPIN", type="password")

if st.sidebar.button("🔑 Connect"):
    otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
    smart_obj = SmartConnect(api_key=API_KEY)
    login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected = True
        st.session_state.obj = smart_obj
        st.session_state.token_df = load_tokens()
        st.sidebar.success("✅ System Live!")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df
    lot_size = 50 if index == "NIFTY" else 15
    total_qty = lot_size * int(qty_multiplier)

    # 1. SPOT DATA FETCH
    t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
    t_tok = "26000" if index=="NIFTY" else "26009"
    res = obj.ltpData("NSE", t_name, t_tok)
    
    if res.get('status'):
        spot = float(res['data']['ltp'])
        st.session_state.price_history.append(spot)
        if len(st.session_state.price_history) > 10: st.session_state.price_history.pop(0)
        sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)
        atm = int(round(spot / (50 if index=="NIFTY" else 100)) * (50 if index=="NIFTY" else 100))

        # 2. FETCH OI & VOLUME DATA
        search_prefix = f"{index}{expiry_str}{atm}"
        ce_row = df[df['symbol'] == f"{search_prefix}CE"].iloc[0]
        pe_row = df[df['symbol'] == f"{search_prefix}PE"].iloc[0]
        
        # Using getMarketData for OI and Volume
        m_data = obj.getMarketData("FULL", {"NFO": [str(ce_row['token']), str(pe_row['token'])]})
        
        ce_ltp, ce_oi, ce_vol = 0.0, 0, 0
        pe_ltp, pe_oi, pe_vol = 0.0, 0, 0

        if m_data.get('status'):
            for item in m_data['data']['fetched']:
                if item['symbolToken'] == str(ce_row['token']):
                    ce_ltp, ce_oi, ce_vol = item['lastTradedPrice'], item['opnInterest'], item['volume']
                else:
                    pe_ltp, pe_oi, pe_vol = item['lastTradedPrice'], item['opnInterest'], item['volume']

        # 📊 3. CHECKLIST LOGIC
        st.subheader("📋 Trade Confirmation Checklist")
        c_trend, c_sent = (spot > sma), (ce_ltp > pe_ltp)
        c_oi, c_vol = (ce_oi > pe_oi), (ce_vol > pe_vol) # Strict Volume/OI Logic

        p_trend, p_sent = (spot < sma), (pe_ltp > ce_ltp)
        p_oi, p_vol = (pe_oi > ce_oi), (pe_vol > ce_vol)

        ce_safety = round((sum([c_trend, c_sent, c_oi, c_vol]) / 4) * 100, 1)
        pe_safety = round((sum([p_trend, p_sent, p_oi, p_vol]) / 4) * 100, 1)

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"🟢 **CALL Checklist ({ce_safety}%)**")
            st.write(f"Price > SMA: {'✅' if c_trend else '❌'}")
            st.write(f"CE OI > PE OI: {'✅' if c_oi else '❌'}")
            st.write(f"CE Vol > PE Vol: {'✅' if c_vol else '❌'}")
        with col2:
            st.write(f"🔴 **PUT Checklist ({pe_safety}%)**")
            st.write(f"Price < SMA: {'✅' if p_trend else '❌'}")
            st.write(f"PE OI > CE OI: {'✅' if p_oi else '❌'}")
            st.write(f"PE Vol > CE Vol: {'✅' if p_vol else '❌'}")

        # 🚀 4. EXECUTION ENGINE
        if st.session_state.active_trade is None:
            if auto_trade:
                if ce_safety >= 75.0:
                    order_id = obj.placeOrder({"variety":"NORMAL", "tradingsymbol":ce_row['symbol'], "symboltoken":str(ce_row['token']), "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                    st.session_state.active_trade = {'type':'CE', 'entry_spot':spot, 'target_spot':spot+tgt_points, 'sl_spot':spot-sl_points, 'symbol':ce_row['symbol']}
                    st.success(f"🤖 Auto-Trade: CALL BOUGHT! ID: {order_id}")
                elif pe_safety >= 75.0:
                    order_id = obj.placeOrder({"variety":"NORMAL", "tradingsymbol":pe_row['symbol'], "symboltoken":str(pe_row['token']), "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                    st.session_state.active_trade = {'type':'PE', 'entry_spot':spot, 'target_spot':spot-tgt_points, 'sl_spot':spot+sl_points, 'symbol':pe_row['symbol']}
                    st.success(f"🤖 Auto-Trade: PUT BOUGHT! ID: {order_id}")

        else:
            # Monitoring Active Trade
            trade = st.session_state.active_trade
            pnl = round(spot - trade['entry_spot'] if trade['type'] == 'CE' else trade['entry_spot'] - spot, 2)
            st.info(f"🚀 Active: {trade['symbol']} | P&L: {pnl} Points")
            
            # Exit Logic
            if (trade['type'] == 'CE' and (spot >= trade['target_spot'] or spot <= trade['sl_spot'])) or \
               (trade['type'] == 'PE' and (spot <= trade['target_spot'] or spot >= trade['sl_spot'])):
                res_msg = "✅ Target" if pnl > 0 else "❌ SL"
                st.session_state.trade_history.append({"Trade": trade['symbol'], "PnL": pnl, "Result": res_msg})
                st.session_state.active_trade = None
                st.rerun()

        # 📚 5. HISTORY
        if st.session_state.trade_history:
            st.divider()
            st.subheader("📚 Trade History")
            st.table(pd.DataFrame(st.session_state.trade_history))

    time.sleep(2)
    st.rerun()
