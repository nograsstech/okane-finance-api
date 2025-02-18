import os
import json
import datetime
import requests
from app.base.utils.mongodb import connect_mongodb, COLLECTIONS
from app.news.dto import AlphaVantageNewsQueryDTO
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

"""
Mock response for AlphaVantage News and Sentiment API for testing purposes
"""


async def get_mock_news_sentiment():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(
        dir_path, "example/alphavantage_news_sentiment_response_example.json")
    with open(file_path) as f:
        return json.load(f)


"""
This function is called when the user makes a GET request to /news/
:param params: the query parameters from the GET request following AlphaVantageNewsQueryDTO
"""


async def fetch_alpha_vantage_news(_params: AlphaVantageNewsQueryDTO):
    db = await connect_mongodb()
    collection = db[COLLECTIONS["news_with_sentiment"]]

    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": os.environ["ALPHA_VANTAGE_API_KEY"],
        "from_date": _params.get('from_date'),
        "to_date": _params.get('to_date'),
        "tickers": _params.get('tickers'),
        "limit": _params.get('limit'),
        "sort": "RELEVANCE",
    }

    # Remove keys with None values
    params = {k: v for k, v in params.items() if (
        v != None or v != "")}

    # fetch news and sentiment data
    r = requests.get(base_url, params=params)
    data = r.json()

    # ------------------------------------------
    # # read json file for mock response
    # data = await get_mock_news_sentiment()
    # ------------------------------------------

    # loop through the feed and convert time_published to time format (from string)
    for news in data["feed"]:
        time_published = news["time_published"]
        news["time_published"] = datetime.datetime.strptime(
            time_published, "%Y%m%dT%H%M%S"
        ).isoformat()

        for topic in news["topics"]:
            score = topic["relevance_score"]
            topic["relevance_score"] = float(score)

        for sentiment in news["ticker_sentiment"]:
            relevance_score = sentiment["relevance_score"]
            sentiment_score = sentiment["ticker_sentiment_score"]
            sentiment["relevance_score"] = float(relevance_score)
            sentiment["ticker_sentiment_score"] = float(sentiment_score)

    # save the data to mongodb
    try:
        collection.insert_many(data["feed"])
    except Exception as e:
        return {
            # HTTP 400 status
            "status": HTTP_400_BAD_REQUEST,
            "message": f"Failed to archive news and sentiment data to MongoDB. Error: {e}",
        }

    return {
        # HTTP 200 status
        "status": HTTP_200_OK,
        "message": "Successfully archived news and sentiment data to MongoDB",
    }


async def fetch_alpha_vantage_news_6h():
    # from is now - 6 hours, formatted as YYYYMMDDTHHmm
    _date_utc = datetime.datetime.now(datetime.timezone.utc)
    _from_date = (_date_utc - datetime.timedelta(hours=6)
                  ).strftime("%Y%m%dT%H%M")
    _to_date = _date_utc.strftime("%Y%m%dT%H%M")
    _params = {
        "from_date": _from_date,
        "to_date": _to_date,
        "tickers": "",
        "limit": 1000,
        "sort": "RELEVANCE",
    }
    res = await fetch_alpha_vantage_news(_params)
    return res

async def get_news_sentiment_per_period_by_ticker(ticker: str):
    """
    Analyzes news sentiment for a given ticker over various time intervals and provides historical weekly sentiment.

    Args:
        ticker (str): The stock ticker symbol to analyze (e.g., "AAPL").

    Returns:
        Dict[str, Any]: A dictionary containing sentiment analysis results.
            - For each time interval ("6 hours", "1 day", "1 week", "1 month", "3 months"),
              the dictionary includes a "timeframe" key with the average sentiment score.
              Example: {"6 hours": {"timeframe": 0.75}, "1 day": {"timeframe": 0.60}, ...}
            - Includes a "weekly_sentiment" key containing the average sentiment score for each of the past 10 weeks.
              Example: {"weekly_sentiment": {"1 week ago": 0.80, "2 weeks ago": 0.70, ...}}
    """
    db = await connect_mongodb()
    collection = db[COLLECTIONS["news_with_sentiment"]]

    intervals = {
        "6 hours": {"hours": 6},
        "1 day": {"days": 1},
        "1 week": {"days": 7},
        "1 month": {"days": 30},
        "3 months": {"days": 90},
    }

    results = {}

    for interval_name, interval_delta in intervals.items():
        _date_utc = datetime.datetime.utcnow()
        from_date = (_date_utc - datetime.timedelta(**interval_delta)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        print(from_date)
        news = collection.find({
            "ticker_sentiment": {
                "$elemMatch": {
                    "ticker": ticker
                }
            },
            "time_published": {
                "$gte": from_date,
            }
        })
        # Extract overall_sentiment_score from each document
        sentiment_scores = [doc["overall_sentiment_score"] for doc in news]
        # Calculate the average sentiment score
        average_sentiment_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        results[interval_name] = {"timeframe": average_sentiment_score}
    
    # Calculate weekly sentiment for the past 10 weeks
    weekly_sentiments = {}
    for i in range(1, 11):
        week_name = f"{i} week{'s' if i > 1 else ''} ago"
        _date_utc = datetime.datetime.utcnow()
        from_date = (_date_utc - datetime.timedelta(days=i * 7)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_date = (_date_utc - datetime.timedelta(days=(i - 1) * 7)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        news = collection.find({
            "ticker_sentiment": {
                "$elemMatch": {
                    "ticker": ticker
                }
            },
            "time_published": {
                "$gte": from_date,
                "$lt": to_date,
            }
        })
        
        sentiment_scores = [doc["overall_sentiment_score"] for doc in news]
        average_sentiment_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        weekly_sentiments[week_name] = average_sentiment_score

    results["weekly_sentiment"] = weekly_sentiments
    return results
