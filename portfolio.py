import json
import os
from analyzer import process_stock

PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=4)

def add_position(ticker, shares, buy_price, currency="DKK"):
    portfolio = load_portfolio()
    # Check if ticker already exists to update it, or just append
    for pos in portfolio:
        if pos['ticker'].upper() == ticker.upper():
            # Update position
            pos['shares'] = shares
            pos['buy_price'] = buy_price
            pos['currency'] = currency
            save_portfolio(portfolio)
            return
            
    portfolio.append({
        "ticker": ticker.upper(),
        "shares": shares,
        "buy_price": buy_price,
        "currency": currency
    })
    save_portfolio(portfolio)

def remove_position(ticker):
    portfolio = load_portfolio()
    portfolio = [p for p in portfolio if p['ticker'].upper() != ticker.upper()]
    save_portfolio(portfolio)

def analyze_portfolio():
    """
    Returns the portfolio enriched with live analysis, P/L, and action recommendation.
    """
    portfolio = load_portfolio()
    analyzed = []
    
    for pos in portfolio:
        ticker = pos['ticker']
        buy_price = pos['buy_price']
        shares = pos['shares']
        currency = pos.get('currency', 'DKK')
        
        # Analyze using custom buy price
        df, signal_data = process_stock(ticker, period="1y", user_buy_price=buy_price)
        
        if signal_data is None:
            continue
            
        latest_close = signal_data['latest_close']
        targets = signal_data.get('targets')
        
        action = "HOLD"
        action_color = "gray"
        
        # Determine status
        if targets:
            if latest_close <= targets['stop_loss']:
                action = "SÆLG (Stop-Loss ramt)"
                action_color = "red"
            elif latest_close >= targets['take_profit']:
                action = "SÆLG (Take-Profit ramt)"
                action_color = "green"
            elif signal_data['score'] <= -2:
                action = "SÆLG (Trend vendt)"
                action_color = "red"
            else:
                action = "HOLD (Kører efter planen)"
                action_color = "blue"
        else:
            # Hvis targets mangler (pga ekstrem SÆLG rating)
            if signal_data['score'] <= -2:
                action = "SÆLG (Dårlig Trend)"
                action_color = "red"
            
        # P/L udregning
        current_value = latest_close * shares
        invested_value = buy_price * shares
        profit_loss = current_value - invested_value
        profit_loss_pct = ((latest_close - buy_price) / buy_price) * 100
        
        analyzed.append({
            "ticker": ticker,
            "shares": shares,
            "buy_price": buy_price,
            "currency": currency,
            "current_price": latest_close,
            "current_value": current_value,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
            "stop_loss": targets['stop_loss'] if targets else None,
            "take_profit": targets['take_profit'] if targets else None,
            "action": action,
            "action_color": action_color,
            "score": signal_data['score']
        })
        
    return analyzed
