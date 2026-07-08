import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

def get_stock_data(ticker, period="2y"):
    """
    Henter historisk data for en given aktie ticker via yfinance.
    Justerer intervallet afhængigt af perioden for at have nok datapunkter (minimum >20 rækker).
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Bestem det optimale interval
        interval = "1d"
        if period == "1d":
            interval = "5m" # 5-minutters candles for en dag (~78 rækker pr. dag)
        elif period == "1wk":
            interval = "15m" # 15-min candles for en uge (~130 rækker)
        elif period == "1mo":
            interval = "1h" # 1-times candles for en måned (~150 rækker)
        elif period == "3mo":
            interval = "1d" # Daglige candles for 3 mdr (~60 rækker)
            
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return None
            
        return df
    except Exception as e:
        print(f"Fejl ved hentning af data for {ticker}: {e}")
        return None

def calculate_indicators(df):
    """
    Beregner de tekniske indikatorer (SMA, RSI, MACD, ATR).
    """
    if df is None or df.empty:
        return df
        
    close_prices = df['Close']
    
    # Simple Moving Averages (SMA)
    df['SMA_20'] = SMAIndicator(close=close_prices, window=20).sma_indicator()
    df['SMA_50'] = SMAIndicator(close=close_prices, window=50).sma_indicator()
    df['SMA_200'] = SMAIndicator(close=close_prices, window=200).sma_indicator()
    
    # Relative Strength Index (RSI)
    df['RSI'] = RSIIndicator(close=close_prices, window=14).rsi()
    
    # Moving Average Convergence Divergence (MACD)
    macd = MACD(close=close_prices, window_slow=26, window_fast=12, window_sign=9)
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    # Average True Range (ATR) - Volatilitet
    atr = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ATR'] = atr.average_true_range()
    
    return df

def generate_signal(df, user_buy_price=0.0):
    """
    Point-system skaleret til at fungere uden lang historik.
    """
    if df is None or len(df) < 14:
        latest_close = df.iloc[-1]['Close'] if df is not None and not df.empty else 0.0
        return {"score": 0, "signal": "Neutral", "reasoning": "Ikke nok data til overhovedet at beregne basale indikatorer (kræver >14 dage).", "targets": None, "latest_close": latest_close}
        
    latest = df.iloc[-1]
    
    score = 0
    max_possible_score = 0
    reasons = []
    
    is_macro_uptrend = False
    
    # 1. Makro Trend Analyse (SMA200)
    if pd.notna(latest['SMA_200']):
        max_possible_score += 2
        if latest['Close'] > latest['SMA_200']:
            score += 2
            is_macro_uptrend = True
            reasons.append("🟢 Prisen er over det lange 200-dages snit (Stærk makro-trend).")
        else:
            score -= 2
            reasons.append("🔴 Prisen er under det lange 200-dages snit (Svag makro-trend).")
    else:
        reasons.append("⚪ Data-historik for kort til 200-dages glidende gennemsnit.")

    # 2. Mellem Trend Analyse (SMA50)
    if pd.notna(latest['SMA_50']):
        max_possible_score += 1
        if latest['Close'] > latest['SMA_50']:
            score += 1
            reasons.append("🟢 Prisen er over 50-dages snittet (Positiv mellemlang trend).")
        else:
            score -= 1
            reasons.append("🔴 Prisen er under 50-dages snittet (Negativ mellemlang trend).")
    else:
        reasons.append("⚪ Data-historik for kort til 50-dages glidende gennemsnit.")
            
    # 3. Momentum Analyse (MACD)
    if pd.notna(latest['MACD']) and pd.notna(latest['MACD_Signal']):
        max_possible_score += 1
        if latest['MACD'] > latest['MACD_Signal']:
            score += 1
            reasons.append("🟢 MACD ligger over sin signallinje (Bullish momentum).")
        else:
            score -= 1
            reasons.append("🔴 MACD ligger under sin signallinje (Bearish momentum).")

    # 4. Klogere RSI Analyse ("Buy the dip")
    if pd.notna(latest['RSI']):
        max_possible_score += 1
        if latest['RSI'] > 75:
            score -= 1
            reasons.append(f"🔴 RSI er meget høj ({latest['RSI']:.0f}). Aktien er ekstremt overkøbt.")
        elif is_macro_uptrend and latest['RSI'] < 50:
            score += 1
            reasons.append(f"🟢 RSI er {latest['RSI']:.0f}. Dette ligner et sundt 'dip' i en stærk opadgående trend (Købsmulighed).")
        elif not is_macro_uptrend and latest['RSI'] < 30:
            score += 1
            reasons.append(f"🟢 RSI er under 30 ({latest['RSI']:.0f}). Aktien er oversolgt og kan bounce.")
        else:
            reasons.append(f"🟡 RSI er {latest['RSI']:.0f} (Neutral zone).")

    # Skalér scoren så den passer til den gamle 5-punkts skala
    if max_possible_score > 0:
        scaled_score = (score / max_possible_score) * 5
    else:
        scaled_score = 0

    # Konklusion baseret på skaleret score
    if scaled_score >= 4:
        signal = "STÆRK KØB"
        summary = "Aktien/ETF'en viser overordnet stærk fremgang ift. den valgte tidsperiode."
    elif scaled_score >= 2:
        signal = "KØB"
        summary = "Trenden er generelt positiv for den valgte horisont."
    elif scaled_score >= 0:
        signal = "NEUTRAL / HOLD"
        summary = "Markedet er ubeslutsomt, eller aktivet konsoliderer."
    elif scaled_score >= -2:
        signal = "SÆLG"
        summary = "Trenden er vendt til det negative på den valgte horisont."
    else:
        signal = "STÆRK SÆLG"
        summary = "Alle aktive indikatorer peger nedad. Høj risiko ift. den valgte horisont."
        
    reasoning_text = "\n".join(reasons) + f"\n\n**Samlet Vurdering:** {summary}"
    
    # Beregn Risk Management Targets 
    # Vises altid for at give brugeren et referencepunkt
    targets = None
    if pd.notna(latest['ATR']):
        atr = latest['ATR']
        is_custom = user_buy_price > 0
        
        if is_custom:
            buy_price = user_buy_price
        else:
            # Algoritmens Anbefalede Limit-køb:
            # Prøv at købe ved den korte trend (SMA20) for at undgå at købe toppen af et pludseligt ryk opad.
            # Ligger prisen allerede under SMA20, køber vi til dagens aktuelle pris.
            sma_20 = latest['SMA_20'] if pd.notna(latest['SMA_20']) else latest['Close']
            buy_price = min(latest['Close'], sma_20)
        
        stop_loss = buy_price - (1.5 * atr)
        take_profit = buy_price + (3.0 * atr)
        
        targets = {
            "buy_price": buy_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "atr": atr,
            "is_custom": is_custom
        }
    
    return {
        "score": score,
        "signal": signal,
        "reasoning": reasoning_text,
        "latest_close": latest['Close'],
        "targets": targets
    }

def process_stock(ticker, period="2y", user_buy_price=0.0):
    """
    Kører hele flowet for en aktie og returnerer dataframe samt signal.
    """
    df = get_stock_data(ticker, period)
    if df is not None:
        df = calculate_indicators(df)
        signal_data = generate_signal(df, user_buy_price)
        
        if period == "6mo":
            cutoff_date = df.index[-1] - pd.Timedelta(days=180)
            df = df[df.index >= cutoff_date]
        elif period == "1y":
            cutoff_date = df.index[-1] - pd.Timedelta(days=365)
            df = df[df.index >= cutoff_date]
            
        return df, signal_data
    return None, None
