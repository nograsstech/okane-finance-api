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
        v is not None or v is not "")}

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
    _date_utc = datetime.datetime.utcnow()
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
