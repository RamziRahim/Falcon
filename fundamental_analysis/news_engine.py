"""
===============================================================================
Falcon AI Swing Trading Platform — Corporate Catalyst News Engine
===============================================================================
Script      : news_engine.py
Package     : Fundamental Analysis
===============================================================================
"""
from __future__ import annotations
import yfinance as yf

class NewsEngine:
    def get_ticker_catalysts(self, ticker: str, max_headlines: int = 5) -> str:
        """
        Directly streams targeted news footprints using precise ticker objects, 
        completely avoiding global macro search index pollution traps.
        """
        # Formulate search term cleanly for Indian listings
        formatted_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        fallback_msg = "• No critical near-term corporate catalyst headlines identified in open-source streams."
        
        try:
            # Instantiate Ticker directly to target its isolated news array
            stock = yf.Ticker(formatted_ticker)
            news_list = stock.news
            
            if not news_list:
                # Secondary fallback to plain token name if .NS returns zero feeds
                if ".NS" in formatted_ticker:
                    stock = yf.Ticker(ticker.replace(".NS", ""))
                    news_list = stock.news

            if not news_list:
                return fallback_msg
                
            formatted_headlines = []
            for article in news_list[:max_headlines]:
                title = article.get("title", "").strip()
                publisher = article.get("publisher", "Unknown Source").strip()
                
                if title:
                    formatted_headlines.append(f"• {title} [{publisher}]")
                    
            if not formatted_headlines:
                return fallback_msg
                
            return "\n".join(formatted_headlines)
            
        except Exception as e:
            print(f"[NEWS ENGINE WARNING] Failed to harvest catalyst stream for {ticker}: {e}")
            return fallback_msg

news_engine = NewsEngine()