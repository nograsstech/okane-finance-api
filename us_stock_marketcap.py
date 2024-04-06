import asyncio
import datetime
from loguru import logger
import aiohttp
import csv
import pandas as pd
from io import StringIO
import os

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

COLLECTIONS = {
    "stock_lists": "stock_lists",
    "news": "news",
}


async def connect_mongodb():
  uri = f"mongodb+srv://chuwong35122:iyS6ZUjw0KWhMtB4@develop.dkur4lg.mongodb.net/?retryWrites=true&w=majority"
#   uri = f"mongodb+srv://{os.environ['USER']}:os.{os.environ['PASSWORD']
#                                                  }@develop.dkur4lg.mongodb.net/?retryWrites=true&w=majority"


  # Create a new client and connect to the server
  client = MongoClient(uri, server_api=ServerApi('1'))

  # Send a ping to confirm a successful connection
  try:
      client.admin.command('ping')
      print("Pinged your deployment. You successfully connected to MongoDB!")
  except Exception as e:
      print(e)

  return client['develop']


async def get_companies_marketcap_text():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://companiesmarketcap.com/?download=csv") as response:
            return await response.text()


async def save_companies_marketcap_as_csv(text, date):
  csv_reader = csv.reader(StringIO(text))
  data = list(csv_reader)

  # Specify the output CSV file path
  csv_output_path = f'data/us-stock-list/{date}.csv'

  # Write data to a CSV file
  with open(csv_output_path, 'w', newline='') as csv_file:
      csv_writer = csv.writer(csv_file)
      csv_writer.writerows(data)

  logger.info(f'CSV file "{csv_output_path}" created successfully.')


async def main():
    last_month = datetime.datetime.now() - datetime.timedelta(days=31)
    last_month = last_month.strftime("%d-%m-%Y")

    try:
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        logger.add(f"Start inserting US Stocks on {date}")

        companies_list = await get_companies_marketcap_text()
        await save_companies_marketcap_as_csv(companies_list, date)

        data = pd.read_csv(f"data/us-stock-list/{date}.csv")
        top_150 = data.head(150)

        db = await connect_mongodb()
        collection = db[COLLECTIONS["stock_lists"]]

        # delete last month data
        delete_target = last_month
        cursor = collection.find({"date": delete_target})

        for doc in cursor:
            print(doc)
            collection.delete_one({"_id": doc["_id"]})

            # find the file and delete it
            if os.path.exists(f"data/us-stock-list/{last_month}.csv"):
                os.remove(f"data/us-stock-list/{last_month}.csv")

            logger.info(f"Deleted US Stocks on {last_month}")

        # insert top 150 companies
        insert_data = {
            "date": date,
            "data": top_150.to_dict('records'),
        }
        id = collection.insert_one(insert_data).inserted_id
        logger.success(f"Inserted US Stocks on {date} with ID: {id}")


    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
