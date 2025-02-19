from langchain_core.tools import Tool
from app.news.service import fetch_yfinance_news

'''Tool for fetching news for the provided ticker from Yahoo Finance.'''
fetch_yfinance_news = Tool(
  name="fetch_yfinance_news",
  func=fetch_yfinance_news,  # Async function
  coroutine=fetch_yfinance_news,  # Required for async tools
  description="Fetches news for the provided ticker from Yahoo Finance.",
)