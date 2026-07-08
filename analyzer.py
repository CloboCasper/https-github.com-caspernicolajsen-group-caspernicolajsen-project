import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

def get_stock_data(ticker, period="2y"):
    """
    Henter historisk data for en given aktie ticker via yfinance.
    Henter minimum 2 år for at kunne beregne SMA200 korrekt.
    """
    try:
        stock = yf.Ticker(ticker)
        fetch_period = period
        if period in ["6mo", "1y"]:
            fetch_period = "2y"
            
        df = stock.history(period=fetch_period)
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
    Point-system (Max +5 / Min -5):
    1. Makro Trend (SMA200): +2 / -2
    2. Mellem Trend (SMA50): +1 / -1
    3. Momentum (MACD): +1 / -1
    4. Klogere RSI: +1 (Buy the dip i uptrend) / -1 (Ekstremt overkøbt)
    """
    if df is None or len(df) < 200:
        return {"score": 0, "signal": "Neutral", "reasoning": "Ikke nok data til en pålidelig analyse (kræver >200 dage).", "targets": None}
        
    latest = df.iloc[-1]
    
    score = 0
    reasons = []
    
    is_macro_uptrend = False
    
    # 1. Makro Trend Analyse (SMA200)
    if pd.notna(latest['SMA_200']):
        if latest['Close'] > latest['SMA_200']:
            score += 2
            is_macro_uptrend = True
            reasons.append("🟢 Prisen er over det lange 200-dages snit (Stærk makro-trend).")
        else:
            score -= 2
            reasons.append("🔴 Prisen er under det lange 200-dages snit (Svag makro-trend).")

    # 2. Mellem Trend Analyse (SMA50)
    if pd.notna(latest['SMA_50']):
        if latest['Close'] > latest['SMA_50']:
            score += 1
            reasons.append("🟢 Prisen er over 50-dages snittet (Positiv mellemlang trend).")
        else:
            score -= 1
            reasons.append("🔴 Prisen er under 50-dages snittet (Negativ mellemlang trend).")
            
    # 3. Momentum Analyse (MACD)
    if pd.notna(latest['MACD']) and pd.notna(latest['MACD_Signal']):
        if latest['MACD'] > latest['MACD_Signal']:
            score += 1
            reasons.append("🟢 MACD ligger over sin signallinje (Bullish momentum).")
        else:
            score -= 1
            reasons.append("🔴 MACD ligger under sin signallinje (Bearish momentum).")

    # 4. Klogere RSI Analyse ("Buy the dip")
    if pd.notna(latest['RSI']):
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

    # Konklusion baseret på samlet score
    if score >= 4:
        signal = "STÆRK KØB"
        summary = "Aktien er i en solid opadgående trend, og momentum er med dig."
    elif score >= 2:
        signal = "KØB"
        summary = "Den generelle trend er positiv. Et godt tidspunkt at akkumulere på."
    elif score >= 0:
        signal = "NEUTRAL / HOLD"
        summary = "Markedet er ubeslutsomt, eller aktien er ved at konsolidere. Hold øje med retningen."
    elif score >= -2:
        signal = "SÆLG"
        summary = "Trenden er vendt til det negative, eller momentum er forsvundet."
    else:
        signal = "STÆRK SÆLG"
        summary = "Alle væsentlige trends og momentum-indikatorer peger nedad. Høj risiko."
        
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
