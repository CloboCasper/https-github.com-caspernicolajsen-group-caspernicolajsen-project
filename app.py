import streamlit as st
import plotly.graph_objects as go
from analyzer import process_stock
from backtester import run_backtest
import portfolio
import requests
import os

API_URL = os.environ.get("API_URL", "https://casper-aktie-api-123.onrender.com")

st.set_page_config(page_title="Aktie Analyse Algoritme", layout="wide", page_icon="📈")

# ==========================================
# SEKTION 0: BRUGER LOGIN & GÆST (SIDEBAR)
# ==========================================
st.sidebar.title("🔐 Din Konto")

if "user_token" not in st.session_state:
    st.session_state.user_token = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "guest_portfolio" not in st.session_state:
    st.session_state.guest_portfolio = []

if st.session_state.user_token:
    st.sidebar.success("Du er logget ind! 🚀")
    if st.sidebar.button("Log Ud"):
        st.session_state.user_token = None
        st.session_state.user_id = None
        st.rerun()
else:
    auth_mode = st.sidebar.radio("Vælg", ["Gæst", "Log Ind", "Opret Bruger"])
    
    if auth_mode in ["Log Ind", "Opret Bruger"]:
        with st.sidebar.form("auth_form"):
            email = st.text_input("Email")
            password = st.text_input("Adgangskode", type="password")
            submitted = st.form_submit_button(auth_mode)
            
            if submitted:
                if auth_mode == "Opret Bruger":
                    try:
                        res = requests.post(f"{API_URL}/api/register", json={"email": email, "password": password})
                        if res.status_code == 200:
                            st.success("Bruger oprettet! Log ind nu.")
                        else:
                            st.error(res.json().get("detail", "Fejl ved oprettelse"))
                    except Exception as e:
                        st.error(str(e))
                elif auth_mode == "Log Ind":
                    try:
                        res = requests.post(f"{API_URL}/api/login", json={"email": email, "password": password})
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state.user_token = data["access_token"]
                            st.session_state.user_id = data["user_id"]
                            st.rerun()
                        else:
                            st.error(res.json().get("detail", "Forkert login"))
                    except Exception as e:
                        st.error(str(e))
    else:
        st.sidebar.info("Du kigger med som Gæst. Dine aktier gemmes ikke i skyen.")

# ==========================================
# SEKTION 0.5: JURIDISK POPUP
# ==========================================
if "accepted_terms" not in st.session_state:
    st.session_state.accepted_terms = False

if not st.session_state.accepted_terms:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>⚠️ Vigtig Information</h1>", unsafe_allow_html=True)
    st.warning("**Velkommen til AktieApp!**\n\nAl information og analyse i denne app er udelukkende til informationsbrug. Historiske afkast er ingen garanti for fremtidige resultater.\n\nAl handel med værdipapirer og krypto indebærer risiko for tab, og du investerer fuldt ud på eget ansvar.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Jeg forstår og accepterer", type="primary", use_container_width=True):
            st.session_state.accepted_terms = True
            st.rerun()
    st.stop()

# ==========================================
# STYLING
# ==========================================
st.markdown("""
<style>
    .metric-container {
        background-color: #1e1e1e;
        color: white; /* Sikrer at teksten altid er hvid uanset browser theme */
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s;
    }
    .metric-container:hover {
        transform: scale(1.02);
    }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0e1117;
        color: #888;
        text-align: center;
        padding: 10px;
        font-size: 12px;
        border-top: 1px solid #333;
        z-index: 100;
    }
    /* Giver plads til footer */
    .block-container {
        padding-bottom: 80px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 AI Teknisk Aktie Analyse & Portefølje")

# Tabs i toppen
tab1, tab2, tab3, tab4 = st.tabs(["💼 Min Portefølje", "🔍 Analyse & Nyheder", "🌍 Markedsoverblik", "📖 Læring & Guide"])

# ==========================================
# PORTEFØLJE FUNKTIONER
# ==========================================
def fetch_and_analyze_portfolio():
    if st.session_state.user_token:
        # Hent fra Supabase via API
        headers = {"Authorization": f"Bearer {st.session_state.user_token}"}
        try:
            res = requests.get(f"{API_URL}/api/portfolio", headers=headers)
            if res.status_code == 200:
                positions = res.json()
            else:
                return []
        except:
            return []
    else:
        # Gæste mode
        positions = st.session_state.guest_portfolio
        
    if not positions:
        return []
        
    # Analyser via API
    try:
        # Convert DB positions to PositionRequest format
        payload = [{"ticker": p["ticker"], "shares": p["shares"], "buy_price": p["buy_price"], "currency": p["currency"]} for p in positions]
        res = requests.post(f"{API_URL}/api/portfolio/analyze", json=payload)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []

def add_position_logic(ticker, shares, buy_price, currency):
    if st.session_state.user_token:
        headers = {"Authorization": f"Bearer {st.session_state.user_token}"}
        payload = {"ticker": ticker, "shares": shares, "buy_price": buy_price, "currency": currency}
        requests.post(f"{API_URL}/api/portfolio", json=payload, headers=headers)
    else:
        for p in st.session_state.guest_portfolio:
            if p["ticker"].upper() == ticker.upper():
                p["shares"] = shares
                p["buy_price"] = buy_price
                p["currency"] = currency
                return
        st.session_state.guest_portfolio.append({
            "ticker": ticker.upper(), "shares": shares, "buy_price": buy_price, "currency": currency
        })

def remove_position_logic(ticker):
    if st.session_state.user_token:
        headers = {"Authorization": f"Bearer {st.session_state.user_token}"}
        requests.delete(f"{API_URL}/api/portfolio/{ticker}", headers=headers)
    else:
        st.session_state.guest_portfolio = [p for p in st.session_state.guest_portfolio if p["ticker"].upper() != ticker.upper()]

# ==========================================
# TAB 1: PORTEFØLJE
# ==========================================
with tab1:
    st.markdown("Her er dit overblik. Algoritmen analyserer live og fortæller dig, hvis du skal sælge.")
    
    with st.expander("➕ Tilføj ny aktie til porteføljen", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            p_ticker = st.text_input("Ticker (fx VRT)", key="p_ticker")
        with c2:
            p_shares = st.number_input("Antal aktier", min_value=1.0, value=10.0, step=1.0, key="p_shares")
        with c3:
            p_price = st.number_input("Din købspris", min_value=0.1, value=100.0, step=1.0, key="p_price")
        with c4:
            p_currency = st.selectbox("Valuta", ["DKK", "USD", "EUR", "NOK", "SEK"], key="p_currency")
        with c5:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Gem Position", use_container_width=True):
                if p_ticker:
                    add_position_logic(p_ticker, p_shares, p_price, p_currency)
                    st.success(f"Tilføjet {p_ticker} til porteføljen!")
                    st.rerun()

    analyzed_portfolio = fetch_and_analyze_portfolio()

    if not analyzed_portfolio:
        st.info("Din portefølje er tom. Tilføj din første aktie ovenfor.")
    else:
        for pos in analyzed_portfolio:
            with st.container():
                st.markdown(f"#### {pos['ticker']} ({pos['shares']} stk)")
                
                col_a, col_b, col_sl, col_tp, col_c, col_d, col_e = st.columns([1.5, 1.5, 1.2, 1.2, 1.5, 1.5, 2])
                col_a.metric("Nuværende Kurs", f"{pos['current_price']:.2f} {pos['currency']}")
                col_b.metric("Din Købskurs", f"{pos['buy_price']:.2f} {pos['currency']}")
                
                if pos['take_profit']:
                    col_tp.metric("Take Profit", f"{pos['take_profit']:.1f}")
                else:
                    col_tp.metric("Take Profit", "N/A")
                    
                profit_loss = (pos['current_price'] - pos['buy_price']) * pos['shares']
                profit_loss_pct = ((pos['current_price'] - pos['buy_price']) / pos['buy_price']) * 100
                current_value = pos['current_price'] * pos['shares']
                    
                col_c.metric("Afkast (%)", f"{profit_loss_pct:.2f} %", f"{profit_loss_pct:.2f} %")
                col_d.metric("Værdi", f"{current_value:.2f} {pos['currency']}", f"{profit_loss:.2f} {pos['currency']}")
                
                # Actions Box
                bg_color = "#2e7d32" # Mørkegrøn (Hold)
                border_color = "#1b5e20"
                text_color = "white"
                
                if pos['action_color'] == 'red':
                    bg_color = "#c62828" # Rød (Sælg)
                    border_color = "#b71c1c"
                elif pos['action_color'] == 'green':
                    bg_color = "#1b5e20" # Stærk Grøn (Take Profit)
                
                col_e.markdown(f"""
                <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 15px 10px; border-radius: 5px; text-align: center; height: 100%; display: flex; align-items: center; justify-content: center;">
                    <b style="color: {text_color}; font-size: 1.1em;">{pos['action']}</b>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"🗑️ Slet {pos['ticker']}", key=f"del_{pos['ticker']}"):
                    remove_position_logic(pos['ticker'])
                    st.rerun()
                    
                st.markdown("---")

# ==========================================
# TAB 2: ANALYSE & NYHEDER
# ==========================================
with tab2:
    st.markdown("Søg på et navn eller ticker for at se dybdegående analyse og seneste nyheder.")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        search_query = st.text_input("Søg (fx 'Novo' eller 'AAPL')", value="Novo")
        
        # Søgefunktion der rækker ud til Yahoo Finance
        search_results = []
        if len(search_query) > 1:
            try:
                url = "https://query2.finance.yahoo.com/v1/finance/search"
                params = {"q": search_query, "quotesCount": 25, "newsCount": 0}
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, params=params, headers=headers, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    quotes = data.get("quotes", [])
                    for quote in quotes:
                        if quote.get("quoteType") in ["EQUITY", "ETF", "MUTUALFUND", "INDEX"]:
                            search_results.append({
                                "symbol": quote.get("symbol"),
                                "name": quote.get("shortname", quote.get("longname", quote.get("symbol")))
                            })
            except Exception as e:
                st.error(f"Søgefejl: {e}")
                
        ticker_options = [f"{r['name']} ({r['symbol']})" for r in search_results]
        selected_ticker_label = st.selectbox("Vælg Aktie/Krypto", ticker_options) if ticker_options else None
        
        ticker = "NOVO-B.CO"
        if selected_ticker_label:
            ticker = selected_ticker_label.split("(")[-1].replace(")", "")
            
        period = st.selectbox("Periode", ["1d", "1wk", "1mo", "3mo", "6mo", "1y", "2y", "5y"], index=5)
        
        if period in ["1d", "1wk", "1mo", "3mo"]:
            st.warning("⚠️ **Kort Horisont:** Jo kortere en periode der vælges, desto mere kortsigtet (og usikker) er algoritmens trend-analyse. Den reagerer lynhurtigt på små pris-ændringer.")
        
        
        st.markdown("---")
        st.markdown("**Valgfri: Egen Risk Management**")
        user_buy_price = st.number_input("Tjek Stop-Loss ud fra GAK", value=0.0, step=1.0, help="Indtast en fiktiv eller reel købskurs for at se hvor Stop-Loss ville ligge på grafen.")
        
        st.markdown("---")
        analyze_btn = st.button("Analyser", type="primary", use_container_width=True)

    # Gem den valgte ticker i session_state når der trykkes Analyser
    if "current_analysis" not in st.session_state:
        st.session_state.current_analysis = None
        
    if analyze_btn:
        st.session_state.current_analysis = {"ticker": ticker, "period": period, "user_buy_price": user_buy_price}

    if st.session_state.current_analysis:
        ana_ticker = st.session_state.current_analysis["ticker"]
        ana_period = st.session_state.current_analysis["period"]
        ana_ubp = st.session_state.current_analysis["user_buy_price"]
        
        with st.spinner(f"Analyserer {ana_ticker}..."):
            df, signal_data = process_stock(ana_ticker, ana_period, user_buy_price=ana_ubp)
            
            if df is None:
                st.error(f"Kunne ikke finde data for {ana_ticker}. Prøv en anden ticker.")
            else:
                with col2:
                    st.subheader(f"Analyse for {ana_ticker}")
                    
                    # --- Resultat Panel ---
                    score = signal_data['score']
                    signal = signal_data['signal']
                    
                    if score >= 2: color = "#2e7d32"
                    elif score <= -2: color = "#c62828"
                    else: color = "#f57c00"
                        
                    currency_str = signal_data.get('currency', '')
                    
                    st.markdown(f"""
                    <div style="background-color: {color}; padding: 20px; border-radius: 10px; color: white; text-align: center;">
                        <h2>{signal} (Samlet Score: {score}/5)</h2>
                        <p style="font-size: 1.2rem;">Seneste Lukkepris: {signal_data['latest_close']:.2f} {currency_str}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # --- Risk Management Targets ---
                    targets = signal_data.get('targets')
                    if targets:
                        st.markdown("<br>", unsafe_allow_html=True)
                        t1, t2, t3 = st.columns(3)
                        
                        sl_pct = ((targets['stop_loss'] - targets['buy_price']) / targets['buy_price']) * 100
                        tp_pct = ((targets['take_profit'] - targets['buy_price']) / targets['buy_price']) * 100
                        
                        label_buy = "Din Købskurs" if targets['is_custom'] else "Anbefalet Købskurs"
                        
                        t1.metric(label_buy, f"{targets['buy_price']:.2f} {currency_str}")
                        t2.metric("Stop-Loss", f"{targets['stop_loss']:.2f} {currency_str}", f"{sl_pct:.1f}%", delta_color="inverse")
                        t3.metric("Take-Profit", f"{targets['take_profit']:.2f} {currency_str}", f"+{tp_pct:.1f}%", delta_color="normal")
                        
                        info_text = "💡 **Personlig Risk/Reward**" if targets['is_custom'] else "💡 **System Risk/Reward**"
                        st.info(f"{info_text}: Handlen risikerer {abs(sl_pct):.1f}% for at vinde {tp_pct:.1f}%.")
                    
                    st.markdown("### Hvorfor?")
                    st.markdown(signal_data['reasoning'])
                    
                    # --- Grafer ---
                    st.divider()
                    st.subheader("Interaktiv Graf")
                    
                    fig = go.Figure(data=[go.Candlestick(x=df.index,
                                    open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Pris')])
                                    
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))
                    
                    if 'SMA_200' in df.columns:
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='white', width=2, dash='dash'), name='SMA 200 (Makro)'))
                    
                    if targets:
                        last_date = df.index[-1]
                        first_date_in_view = df.index[0]
                        
                        fig.add_shape(type="line", x0=first_date_in_view, y0=targets['stop_loss'], x1=last_date, y1=targets['stop_loss'],
                                      line=dict(color="red", width=2, dash="dot"), name="Stop-Loss")
                        fig.add_shape(type="line", x0=first_date_in_view, y0=targets['take_profit'], x1=last_date, y1=targets['take_profit'],
                                      line=dict(color="green", width=2, dash="dot"), name="Take-Profit")
                                      
                        color_buy = "yellow" if targets['is_custom'] else "white"
                        fig.add_shape(type="line", x0=first_date_in_view, y0=targets['buy_price'], x1=last_date, y1=targets['buy_price'],
                                 line=dict(color=color_buy, width=1, dash="dash"))
                    
                    fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=500, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # --- Backtest ---
                    st.divider()
                    st.subheader("Tillids-test af Algoritmen (Backtest)")
                    
                    with st.expander("ℹ️ Sådan forstår du grafen (Hvorfor er den grønne linje flad?)", expanded=True):
                        st.markdown("""
                        Denne graf viser **ikke** dine personlige tab/gevinster, men viser i stedet: *Hvad ville der være sket med dine penge, hvis du fulgte algoritmens signaler slavisk?*
                        
                        * 📉 **Den Grå Linje (Køb-og-Hold):** Viser hvordan aktien rent faktisk har svinget op og ned i den valgte periode.
                        * 📈 **Det Grønne Område (Algoritmen):** Viser hvordan dine penge ville være vokset (eller faldet) ved at bruge algoritmen.
                        
                        **Hvorfor er det grønne område nogle gange helt fladt på 0%?**
                        Når algoritmen ser en negativ trend, "sælger" den aktien. Mens det grønne område er fladt, har du ganske vist 0% i afkast, men du **undgår også at miste penge** i store fald! Hvis den grå linje falder -40%, og den grønne linje ligger fladt på 0%, har algoritmen i praksis reddet dig fra et kæmpe tab. Et fladt grønt område under en krise er algoritmens største styrke.
                        """)
                        
                    bt_results = run_backtest(df)
                    
                    if bt_results is None:
                        st.warning("Ikke nok data til at køre en meningsfuld backtest.")
                    else:
                        s_ret = bt_results['strategy_return']
                        m_ret = bt_results['market_return']
                        time_in_market = bt_results['time_in_market_pct']
                        
                        # Automatisk dom
                        if s_ret > m_ret + 10:
                            st.success(f"🏆 **Stærkt CV:** Algoritmen reddede dig fra tab eller fangede de store opture markant bedre end bare at holde aktien blindt.")
                        elif s_ret > m_ret:
                            st.success(f"✅ **Godt CV:** Algoritmen slog markedet og holdt generelt risikoen nede.")
                        else:
                            st.warning(f"⚠️ **Svagt CV:** På denne specifikke periode ville du have tjent mere på at købe og holde aktien. Algoritmen var for forsigtig.")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Algoritme Afkast", f"{s_ret:.2f} %", delta=f"{s_ret - m_ret:.2f}% ift. markedet")
                        m2.metric("Køb-og-Hold Afkast", f"{m_ret:.2f} %")
                        m3.metric("Max Drawdown (Fald)", f"{bt_results['max_drawdown']:.2f} %")
                        m4.metric("Tid Investeret", f"{time_in_market:.0f} %")
                        
                        bt_df = bt_results['df']
                        fig_bt = go.Figure()
                        fig_bt.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Cum_Strategy_Return']*100-100, name='Algoritme Afkast (%)', line=dict(color='#2e7d32', width=2), fill='tozeroy'))
                        fig_bt.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Cum_Market_Return']*100-100, name='Køb-og-Hold Afkast (%)', line=dict(color='gray', width=2)))
                        fig_bt.update_layout(template="plotly_dark", height=400, yaxis_title="Afkast (%)", margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_bt, use_container_width=True)
                    
                    # --- Nyheder ---
                    st.divider()
                    st.subheader("📰 Seneste Nyheder (Dansk)")
                    try:
                        news_res = requests.get(f"{API_URL}/api/news/{ticker}")
                        if news_res.status_code == 200:
                            news_items = news_res.json()
                            if news_items:
                                for item in news_items:
                                    with st.container():
                                        st.markdown(f"**[{item['title']}]({item['url']})**")
                                        st.caption(f"{item['publisher']} - {item['published_at']}")
                            else:
                                st.write("Ingen nyheder fundet for denne ticker.")
                    except:
                        st.write("Kunne ikke hente nyheder i øjeblikket.")

# ==========================================
# TAB 3: MARKEDSOVERBLIK
# ==========================================
with tab3:
    st.header("🌍 Markedsoverblik (Top Movers)")
    st.markdown("Dagens vindere, tabere og mest handlede aktier på det amerikanske marked.")
    
    with st.spinner("Henter live markedsdata..."):
        try:
            res = requests.get(f"{API_URL}/api/market-overview")
            data = res.json()
            
            col_g, col_l, col_a = st.columns(3)
            
            with col_g:
                st.subheader("🚀 Top Gainers")
                for m in data.get('gainers', []):
                    color = "#4CAF50" if m['change'] > 0 else "#F44336"
                    url = f"https://finance.yahoo.com/quote/{m['symbol']}"
                    st.markdown(f"<a href='{url}' target='_blank' style='text-decoration: none; color: inherit;'><div class='metric-container'><b>{m['symbol']}</b> - {m['name']}<br><span style='color:{color}; font-size:1.2em;'>{m['price']:.2f} (+{m['change_pct']:.2f}%)</span></div></a><br>", unsafe_allow_html=True)
                    
            with col_l:
                st.subheader("🩸 Top Losers")
                for m in data.get('losers', []):
                    color = "#F44336"
                    url = f"https://finance.yahoo.com/quote/{m['symbol']}"
                    st.markdown(f"<a href='{url}' target='_blank' style='text-decoration: none; color: inherit;'><div class='metric-container'><b>{m['symbol']}</b> - {m['name']}<br><span style='color:{color}; font-size:1.2em;'>{m['price']:.2f} ({m['change_pct']:.2f}%)</span></div></a><br>", unsafe_allow_html=True)
                    
            with col_a:
                st.subheader("🔥 Mest Handlede")
                for m in data.get('active', []):
                    color = "#4CAF50" if m['change'] > 0 else "#F44336"
                    sign = "+" if m['change'] > 0 else ""
                    url = f"https://finance.yahoo.com/quote/{m['symbol']}"
                    st.markdown(f"<a href='{url}' target='_blank' style='text-decoration: none; color: inherit;'><div class='metric-container'><b>{m['symbol']}</b> - {m['name']}<br><span style='color:{color}; font-size:1.2em;'>{m['price']:.2f} ({sign}{m['change_pct']:.2f}%)</span></div></a><br>", unsafe_allow_html=True)
                    
        except:
            st.error("Kunne ikke hente markedsoverblik lige nu.")

# ==========================================
# TAB 4: LÆRING & GUIDE
# ==========================================
with tab4:
    st.header("📖 Læring & Guide")
    st.markdown("Er du ny i aktieverdenen? Her er en simpel forklaring på de vigtigste begreber, som denne app bruger for at hjælpe dig med at investere mere sikkert.")
    
    st.markdown("---")
    
    col_l1, col_l2 = st.columns(2)
    
    with col_l1:
        st.subheader("1. Hvad er et 'Backtest' (Tillids-test)?")
        st.markdown("""
        Et **Backtest** er en måde at teste algoritmen på i datiden. 
        Tænk på det som at sætte algoritmen i en tidsmaskine og lade den handle med aktien de seneste par år.
        - **Køb og Hold:** Det afkast du ville have fået, hvis du bare havde købt aktien og aldrig solgt den (uanset hvor meget den faldt).
        - **Algoritme Afkast:** Det afkast algoritmen ville have skaffet dig ved at sige "Køb" og "Sælg" på de rigtige tidspunkter for at undgå de store tab.
        
        *Målet er at se, om algoritmen historisk har været bedre end bare at holde aktien blindt.*
        """)
        
        st.subheader("3. Hvad er 'Stop-Loss' (Risikostyring)?")
        st.markdown("""
        **Stop-Loss** er dit sikkerhedsnet. Det er den pris, hvor algoritmen siger: "Nu falder aktien for meget, det er bedst at sælge for at undgå at miste flere penge."
        - Appen beregner et **Stop-Loss** baseret på, hvor meget aktien normalt svinger op og ned.
        - Det hjælper med at beskytte dine penge, så et lille fald ikke bliver til et kæmpe tab.
        """)
        
    with col_l2:
        st.subheader("2. Hvad betyder Score (1 til 5)?")
        st.markdown("""
        Appen kigger på forskellige tekniske signaler (trends og pris-svingninger) og giver en samlet score:
        - **+2 til +5 (KØB/HOLD):** Trenden er stærk og opadgående. Aktien ser sund ud.
        - **-2 til -5 (SÆLG/UNDGÅ):** Trenden er nedadgående. Aktien er for risikabel lige nu.
        - **-1 til +1 (NEUTRAL):** Markedet er usikkert. Afvent og se tiden an.
        """)
        
        st.subheader("4. Hvad er 'Take-Profit'?")
        st.markdown("""
        Ligesom Stop-Loss forhindrer store tab, sikrer **Take-Profit**, at du husker at tage dine gevinster, før aktien falder igen.
        - Det er en forudbestemt mål-pris. Når aktien rammer denne pris, anbefaler algoritmen at man overvejer at sælge, eller i det mindste tager en del af profitten hjem.
        """)
        
    st.markdown("---")
    st.subheader("💡 En god huskeregel")
    st.info("""
    Selvom teknisk analyse og algoritmer kan hjælpe med at finde de rigtige tidspunkter at købe og sælge på, 
    er der **ingen krystalkugle** på aktiemarkedet. Brug appen som et støtteværktøj og en hjælpende hånd til at 
    træffe beslutninger, men husk altid, at historisk succes ikke garanterer succes i fremtiden.
    """)

# ==========================================
# FOOTER (LEGAL)
# ==========================================
st.markdown("""
<div class="footer">
    <b>Juridisk Ansvarsfraskrivelse:</b> Al information og analyse i denne app er udelukkende til informationsbrug. Historiske afkast er ingen garanti for fremtidige resultater. Al handel med værdipapirer og krypto indebærer risiko for tab, og du investerer fuldt ud på eget ansvar.
</div>
""", unsafe_allow_html=True)
