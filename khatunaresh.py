import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259" #
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V25", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Strict Checklist Mode")

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

# -- SIDEBAR CONTROLS --
st.sidebar.title("⚙️ Robot Controls")
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots", min_value=1, value=1)

st.sidebar.subheader("🎯 Spot Index Levels")
tgt_points = st.sidebar.number_input("Target Points", value=40)
sl_points = st.sidebar.number_input("StopLoss Points", value=20)
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Start Sniper"):
    otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
    smart_obj = SmartConnect(api_key=API_KEY)
    login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected = True
        st.session_state.obj = smart_obj
        st.session_state.token_df = load_tokens()
        st.sidebar.success("✅ Sniper Online!")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df
    lot_size = 50 if index == "NIFTY" else 15
    total_qty = lot_size * int(qty_multiplier)

    # 1. LIVE SPOT FETCH
    t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
    t_tok = "26000" if index=="NIFTY" else "26009"
    res = obj.ltpData("NSE", t_name, t_tok)
    
    if res.get('status'):
        spot = float(res['data']['ltp'])
        st.session_state.price_history.append(spot)
        if len(st.session_state.price_history) > 10: st.session_state.price_history.pop(0)
        sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)
        atm = int(round(spot / (50 if index=="NIFTY" else 100)) * (50 if index=="NIFTY" else 100))

        # 2. OPTION CHAIN SCAN (OI & VOLUME)
        search_prefix = f"{index}{expiry_str}{atm}"
        try:
            ce_row = df[df['symbol'] == f"{search_prefix}CE"].iloc[0]
            pe_row = df[df['symbol'] == f"{search_prefix}PE"].iloc[0]
            
            # Fetch FULL market data for Volume and OI
            tokens = [str(ce_row['token']), str(pe_row['token'])]
            m_data = obj.getMarketData("FULL", {"NFO": tokens})
            
            ce_ltp, ce_oi, ce_vol = 0.0, 0, 0
            pe_ltp, pe_oi, pe_vol = 0.0, 0, 0

            if m_data.get('status') and m_data.get('data'):
                for item in m_data['data']['fetched']:
                    if item['symbolToken'] == str(ce_row['token']):
                        ce_ltp, ce_oi, ce_vol = item['lastTradedPrice'], item['opnInterest'], item['volume']
                    else:
                        pe_ltp, pe_oi, pe_vol = item['lastTradedPrice'], item['opnInterest'], item['volume']

            # 📋 3. STRICT CHECKLIST LOGIC
            st.subheader("📋 Trade Confirmation Checklist")
            
            # Conditions
            c_price = spot > sma
            c_oi = ce_oi > pe_oi
            c_vol = ce_vol > pe_vol
            c_mom = ce_ltp > pe_ltp

            p_price = spot < sma
            p_oi = pe_oi > ce_oi
            p_vol = pe_vol > ce_vol
            p_mom = pe_ltp > ce_ltp

            ce_score = sum([c_price, c_oi, c_vol, c_mom])
            pe_score = sum([p_price, p_oi, p_vol, p_mom])
            ce_safety = (ce_score / 4) * 100
            pe_safety = (pe_score / 4) * 100

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"### 🟢 CALL Sniper ({ce_safety}%)")
                st.write(f"Trend (Spot > SMA): {'✅' if c_price else '❌'}")
                st.write(f"OI Bias (CE > PE): {'✅' if c_oi else '❌'}")
                st.write(f"Volume (CE > PE): {'✅' if c_vol else '❌'}")
                st.write(f"Momentum (CE > PE): {'✅' if c_mom else '❌'}")
            
            with col_b:
                st.markdown(f"### 🔴 PUT Sniper ({pe_safety}%)")
                st.write(f"Trend (Spot < SMA): {'✅' if p_price else '❌'}")
                st.write(f"OI Bias (PE > CE): {'✅' if p_oi else '❌'}")
                st.write(f"Volume (PE > CE): {'✅' if p_vol else '❌'}")
                st.write(f"Momentum (PE > CE): {'✅' if p_mom else '❌'}")

            # 🚀 4. AUTO-TRADE EXECUTION
            if st.session_state.active_trade is None and auto_trade:
                if ce_safety >= 75.0:
                    obj.placeOrder({"variety":"NORMAL", "tradingsymbol":ce_row['symbol'], "symboltoken":str(ce_row['token']), "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                    st.session_state.active_trade = {'type':'CE', 'entry_spot':spot, 'target_spot':spot+tgt_points, 'sl_spot':spot-sl_points, 'symbol':ce_row['symbol']}
                    st.balloons()
                elif pe_safety >= 75.0:
                    obj.placeOrder({"variety":"NORMAL", "tradingsymbol":pe_row['symbol'], "symboltoken":str(pe_row['token']), "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                    st.session_state.active_trade = {'type':'PE', 'entry_spot':spot, 'target_spot':spot-tgt_points, 'sl_spot':spot+sl_points, 'symbol':pe_row['symbol']}
                    st.snow()

            # 📊 5. MONITORING & EXIT
            if st.session_state.active_trade:
                trade = st.session_state.active_trade
                pnl = round(spot - trade['entry_spot'] if trade['type'] == 'CE' else trade['entry_spot'] - spot, 2)
                st.warning(f"🚀 ACTIVE TRADE: {trade['symbol']} | Live P&L: {pnl} Points")
                
                # Exit conditions
                is_exit = False
                if trade['type'] == 'CE' and (spot >= trade['target_spot'] or spot <= trade['sl_spot']): is_exit = True
                if trade['type'] == 'PE' and (spot <= trade['target_spot'] or spot >= trade['sl_spot']): is_exit = True

                if is_exit or st.button("🚨 Emergency Exit"):
                    st.session_state.trade_history.append({"Trade": trade['symbol'], "Points": pnl, "Result": "✅" if pnl>0 else "❌"})
                    st.session_state.active_trade = None
                    st.rerun()

        except Exception as e:
            st.error(f"Waiting for Option Chain Data... {e}")

    time.sleep(2)
    st.rerun()
