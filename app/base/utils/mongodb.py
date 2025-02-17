from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv
import certifi
load_dotenv()

COLLECTIONS = {
    "stock_lists": "stock_lists",
    "news": "news",
    "news_with_sentiment": "news_with_sentiment",
    "price_histories": "price_histories",
    "ticker_infos": "ticker_infos",
}

async def connect_mongodb():
  uri = f"mongodb+srv://{os.environ['MONGO_USER']}:{os.environ['MONGO_PASSWORD']}@develop.dkur4lg.mongodb.net/?retryWrites=true&w=majority"

  # Create a new client and connect to the server
  # client = MongoClient(uri, server_api=ServerApi('1'))
  client = MongoClient(uri, server_api=ServerApi('1'), tlsCAFile=certifi.where())

  # Send a ping to confirm a successful connection
  try:
      client.admin.command('ping')
      print("Pinged your deployment. You successfully connected to MongoDB!")
  except Exception as e:
      print(e)

  if (os.environ['ENV'] == 'production'):
    return client['production']
  return client['develop']