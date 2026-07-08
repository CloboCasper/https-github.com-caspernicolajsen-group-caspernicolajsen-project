from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import pandas as pd
import json
import math
from typing import List, Optional
import os
from supabase import create_client, Client

from analyzer import process_stock
from backtester import run_backtest
import portfolio

import requests

app = FastAPI(title="Aktie Analyse API")

@app.get("/api/search")
def search_ticker(q: str):
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": q, "quotesCount": 8, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, params=params, headers=headers)
        if res.status_code == 200:
            data = res.json()
            quotes = data.get("quotes", [])
            results = []
            for quote in quotes:
                # Filtrer irrelevante resultater fra og gem ETFs/Aktier
                if quote.get("quoteType") in ["EQUITY", "ETF", "MUTUALFUND", "INDEX"]:
                    results.append({
                        "symbol": quote.get("symbol"),
                        "name": quote.get("shortname", quote.get("longname", quote.get("symbol"))),
                        "type": quote.get("quoteType"),
                        "exchange": quote.get("exchange")
                    })
            return results
        return []
    except Exception as e:
        print(f"Søgefejl: {e}")
        return []

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class AuthRequest(BaseModel):
    email: str
    password: str

class PositionRequest(BaseModel):
    ticker: str
    shares: float
    buy_price: float
    currency: str = "DKK"

@app.get("/api/analyze")
def analyze_endpoint(ticker: str, period: str = "1y", user_buy_price: float = 0.0):
    df, signal_data = process_stock(ticker, period, user_buy_price)
    
    if df is None or signal_data is None:
        raise HTTPException(status_code=404, detail="Kunne ikke hente data for ticker")
        
    # Convert DataFrame to list of dicts for charting
    # We only need Open, High, Low, Close, SMA_20, SMA_50, SMA_200, Date
    df_chart = df.copy()
    df_chart.index = df_chart.index.astype(str) # format YYYY-MM-DD
    
    chart_data = []
    for date, row in df_chart.iterrows():
        chart_data.append({
            "date": str(date).split()[0], # Just the date part
            "open": float(row['Open']) if not math.isnan(row['Open']) else None,
            "high": float(row['High']) if not math.isnan(row['High']) else None,
            "low": float(row['Low']) if not math.isnan(row['Low']) else None,
            "close": float(row['Close']) if not math.isnan(row['Close']) else None,
            "sma_20": float(row['SMA_20']) if not math.isnan(row['SMA_20']) else None,
            "sma_50": float(row['SMA_50']) if not math.isnan(row['SMA_50']) else None,
            "sma_200": float(row['SMA_200']) if ('SMA_200' in row and not math.isnan(row['SMA_200'])) else None
        })
        
    # Process backtest
    bt_results = run_backtest(df)
    backtest_data = None
    if bt_results:
        backtest_data = {
            "strategy_return": bt_results['strategy_return'],
            "market_return": bt_results['market_return'],
            "max_drawdown": bt_results['max_drawdown'],
            "time_in_market_pct": bt_results['time_in_market_pct']
        }
        
    return {
        "ticker": ticker,
        "signal": signal_data,
        "chart_data": chart_data,
        "backtest": backtest_data
    }

@app.post("/api/portfolio/analyze")
def analyze_portfolio_endpoint(positions: List[PositionRequest]):
    analyzed = []
    for pos in positions:
        ticker = pos.ticker
        buy_price = pos.buy_price
        shares = pos.shares
        currency = pos.currency
        
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
            if signal_data['score'] <= -2:
                action = "SÆLG (Dårlig Trend)"
                action_color = "red"
            else:
                action = "HOLD (God Trend)"
                action_color = "green"

        analyzed.append({
            "ticker": ticker,
            "buy_price": buy_price,
            "shares": shares,
            "currency": currency,
            "current_price": latest_close,
            "take_profit": targets['take_profit'] if targets else None,
            "action": action,
            "action_color": action_color,
            "score": signal_data['score']
        })
        
    return analyzed

@app.get("/api/news/{ticker}")
def get_news(ticker: str):
    import yfinance as yf
    from deep_translator import GoogleTranslator
    
    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news[:5] # Get top 5 news
        
        translator = GoogleTranslator(source='auto', target='da')
        translated_news = []
        
        for item in news_items:
            content = item.get('content', {})
            title = content.get('title', '')
            summary = content.get('summary', '')
            provider = content.get('provider', {}).get('displayName', 'Ukendt Kilde')
            url = content.get('clickThroughUrl', {}).get('url', '')
            if not url:
                url = content.get('canonicalUrl', {}).get('url', '')
            
            # Translate if there is text
            da_title = translator.translate(title) if title else ""
            da_summary = translator.translate(summary) if summary else ""
            
            translated_news.append({
                "title": da_title,
                "summary": da_summary,
                "provider": provider,
                "url": url,
                "published_at": content.get('pubDate', '')
            })
            
        return translated_news
    except Exception as e:
        return []

@app.get("/api/search")
def search_ticker(q: str):
    import requests
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        quotes = res.json().get('quotes', [])
        
        results = []
        for quote in quotes:
            symbol = quote.get('symbol')
            shortname = quote.get('shortname', symbol)
            if symbol:
                results.append({"symbol": symbol, "name": shortname})
        return results[:10]
    except Exception as e:
        return []

@app.get("/api/market-overview")
def market_overview():
    import requests
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    def fetch_screener(scr_id):
        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=true&lang=en-US&region=US&scrIds={scr_id}&count=5"
            res = requests.get(url, headers=headers)
            quotes = res.json()['finance']['result'][0]['quotes']
            result = []
            for q in quotes:
                result.append({
                    "symbol": q.get('symbol', ''),
                    "name": q.get('shortName', ''),
                    "price": q.get('regularMarketPrice', {}).get('raw', 0.0),
                    "change": q.get('regularMarketChange', {}).get('raw', 0.0),
                    "change_pct": q.get('regularMarketChangePercent', {}).get('raw', 0.0)
                })
            return result
        except:
            return []

    return {
        "gainers": fetch_screener('day_gainers'),
        "losers": fetch_screener('day_losers'),
        "active": fetch_screener('most_actives')
    }

# --- SUPABASE AUTH & PORTFOLIO ENDPOINTS ---

@app.post("/api/register")
def register(req: AuthRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        response = supabase.auth.sign_up({"email": req.email, "password": req.password})
        if response.user:
            return {"message": "Success", "user_id": response.user.id}
        else:
            raise HTTPException(status_code=400, detail="Kunne ikke oprette bruger")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/login")
def login(req: AuthRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        response = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
        return {"access_token": response.session.access_token, "user_id": response.user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Forkert email eller adgangskode")

def get_user_id(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Manglende token")
    token = authorization.replace("Bearer ", "")
    try:
        user_response = supabase.auth.get_user(token)
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail="Ugyldigt token")

@app.get("/api/portfolio")
def get_portfolio(user_id: str = Depends(get_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        response = supabase.table("portfolios").select("*").eq("user_id", user_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio")
def save_position(pos: PositionRequest, user_id: str = Depends(get_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        existing = supabase.table("portfolios").select("*").eq("user_id", user_id).eq("ticker", pos.ticker.upper()).execute()
        if len(existing.data) > 0:
            supabase.table("portfolios").update({
                "shares": pos.shares,
                "buy_price": pos.buy_price,
                "currency": pos.currency
            }).eq("user_id", user_id).eq("ticker", pos.ticker.upper()).execute()
        else:
            supabase.table("portfolios").insert({
                "user_id": user_id,
                "ticker": pos.ticker.upper(),
                "shares": pos.shares,
                "buy_price": pos.buy_price,
                "currency": pos.currency
            }).execute()
        return {"message": "Success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/portfolio/{ticker}")
def delete_position(ticker: str, user_id: str = Depends(get_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        supabase.table("portfolios").delete().eq("user_id", user_id).eq("ticker", ticker.upper()).execute()
        return {"message": "Success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
