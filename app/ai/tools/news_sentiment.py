from langchain_core.tools import Tool
from app.news.service import get_news_sentiment_per_period_by_ticker

'''Tool for fetching news sentiment analysis for a given stock ticker.'''
news_sentiment_tool = Tool(
    name="get_news_sentiment",
    func=get_news_sentiment_per_period_by_ticker,  # Async function
    coroutine=get_news_sentiment_per_period_by_ticker,  # Required for async tools
    description="Fetches sentiment analysis for a given stock ticker over different time periods.",
)
