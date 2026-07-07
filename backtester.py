import pandas as pd
import numpy as np

def run_backtest(df):
    """
    Kører en forsimplet backtest baseret på en daglig vurdering af indikatorerne,
    nu opdateret til at matche det nye SMA200 "buy the dip" pointsystem.
    """
    if df is None or len(df) < 200:
        return None
        
    df = df.copy()
    
    # Byg score-kolonner (vektoriseret for fart)
    
    # 1. Makro Trend (SMA200): +2 hvis over, -2 hvis under
    score_sma200 = np.where(df['Close'] > df['SMA_200'], 2, -2)
    
    # 2. Mellem Trend (SMA50): +1 hvis over, -1 hvis under
    score_sma50 = np.where(df['Close'] > df['SMA_50'], 1, -1)
    
    # 3. Momentum (MACD): +1 hvis over signal, -1 hvis under
    score_macd = np.where(df['MACD'] > df['MACD_Signal'], 1, -1)
    
    # 4. Klogere RSI ("Buy the dip" i uptrend)
    is_macro_uptrend = df['Close'] > df['SMA_200']
    
    # Default 0
    score_rsi = np.zeros(len(df))
    # Hvis ekstremt overkøbt
    score_rsi = np.where(df['RSI'] > 75, -1, score_rsi)
    # Hvis uptrend og "dip" (< 50)
    score_rsi = np.where(is_macro_uptrend & (df['RSI'] < 50), 1, score_rsi)
    # Hvis downtrend og decideret oversolgt (< 30)
    score_rsi = np.where(~is_macro_uptrend & (df['RSI'] < 30), 1, score_rsi)
    
    # Samlet score per dag
    df['Total_Score'] = score_sma200 + score_sma50 + score_macd + score_rsi
    
    # Strategi: 
    # Køb (position = 1) når score >= 2
    # Sælg / Gå kontant (position = 0) når score <= -1
    # Hold (behold forrige position) ellers
    
    positions = []
    current_pos = 0
    
    for score in df['Total_Score']:
        if pd.isna(score):
            positions.append(0)
            continue
            
        if score >= 2:
            current_pos = 1
        elif score <= -1:
            current_pos = 0
        positions.append(current_pos)
        
    df['Position'] = positions
    
    # Udregn afkast (Returns)
    df['Daily_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Position'].shift(1) * df['Daily_Return']
    
    df['Daily_Return'] = df['Daily_Return'].fillna(0)
    df['Strategy_Return'] = df['Strategy_Return'].fillna(0)
    # Calculate cumulative returns
    cum_strategy_return = (1 + df['Strategy_Return']).cumprod() - 1
    cum_market_return = (1 + df['Daily_Return']).cumprod() - 1
    
    # Calculate Max Drawdown for Strategy
    roll_max = (1 + df['Strategy_Return']).cumprod().cummax()
    drawdown = (1 + df['Strategy_Return']).cumprod() / roll_max - 1
    max_drawdown = drawdown.min()
    
    # Calculate Time in Market
    days_in_market = df['Position'].sum()
    total_days = len(df)
    time_in_market_pct = (days_in_market / total_days) * 100 if total_days > 0 else 0
    
    # Store for plotting
    df['Cum_Strategy_Return'] = cum_strategy_return + 1
    df['Cum_Market_Return'] = cum_market_return + 1
    
    return {
        'strategy_return': cum_strategy_return.iloc[-1] * 100,
        'market_return': cum_market_return.iloc[-1] * 100,
        'max_drawdown': max_drawdown * 100,
        'time_in_market_pct': time_in_market_pct,
        'df': df
    }
