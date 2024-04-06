import yfinance as yf
from app.base.utils.mongodb import connect_mongodb, COLLECTIONS
from starlette.status import HTTP_200_OK
import json


async def get_ticker_price_history(ticker: str):
    db = await connect_mongodb()
    price_histories_collection = db[COLLECTIONS["price_histories"]]

    data = yf.Ticker(ticker)
    history = data.history(period="5y", interval="1d")
    history["Date"] = history.index
    history = history[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    history['Date'] = history['Date'].dt.strftime('%Y-%m-%d')

    histories = []

    for _, h in history.iterrows():
        d = {"time": h["Date"], "open": round(h["Open"], 5), "high": round(h["High"], 5),
             "low": round(h["Low"], 5), "close": round(h["Close"], 5), "volume": round(h["Volume"], 5)}
        histories.append(d)

    # get existing price history data from MongoDB
    existing_price_history = price_histories_collection.find_one({
                                                                 "ticker": ticker})

    data = {
        "ticker": ticker,
        "history": histories,
    }

    # insert new price to Mongodb before removing existing price
    # to prevent race condition of when the data is being fetched
    try:
        price_histories_collection.insert_one(data)
        if existing_price_history:
            price_histories_collection.delete_one(
                {"_id": existing_price_history["_id"]})

    except Exception as e:
        return {
            "status": 400,
            "message": f"Failed to archive price history data to MongoDB. Error: {e}",
        }

    return {
        "status": HTTP_200_OK,
        "message": "Price history data archived successfully",
    }


async def get_ticker_data(ticker: str):
    db = await connect_mongodb()
    ticker_infos_collection = db[COLLECTIONS["ticker_infos"]]

    data = yf.Ticker(ticker)
    info = data.info
    dividend = data.dividends.to_json()

    # show financials:
    income = data.income_stmt.to_json()
    quarterly_income = data.quarterly_income_stmt.to_json()
    balance = data.balance_sheet.to_json()
    quarterly_balance = data.quarterly_balance_sheet.to_json()
    # cash flow statement
    cashflow = data.cashflow.to_json()
    quarterly_cashflow = data.quarterly_cashflow.to_json()

    # show major holders
    major_holders = data.major_holders.to_json()
    institutional_holders = data.institutional_holders.to_json()
    mutualfund_holders = data.mutualfund_holders.to_json()

    # find existing ticker info
    existing_info = ticker_infos_collection.find_one({"ticker": ticker})

    # show news
    news = data.news
    data = {
        "ticker": ticker,
        "info": info,
        "dividend": json.loads(dividend),
        "income": json.loads(income),
        "quarterly_income": json.loads(quarterly_income),
        "balance": json.loads(balance),
        "quarterly_balance": json.loads(quarterly_balance),
        "cashflow": json.loads(cashflow),
        "quarterly_cashflow": json.loads(quarterly_cashflow),
        "major_holders": json.loads(major_holders),
        "institutional_holders": json.loads(institutional_holders),
        "mutualfund_holders": json.loads(mutualfund_holders),
        "news": news,
    }

    try:
        # insert new ticker info to MongoDB
        ticker_infos_collection.insert_one(data)
        # remove existing ticker info from MongoDB
        if existing_info:
            ticker_infos_collection.delete_one({"ticker": ticker})
    except Exception as e:
        return {
            "status": 400,
            "message": f"Failed to archive ticker info data to MongoDB. Error: {e}",
        }

    return {
        "status": 200,
        "message": "Ticker data retrieved successfully",
        "data": data,
    }
