import yfinance as yf
import pandas as pd


def getYFinanceData(ticker, interval, period=None, start=None, end=None):
  """
  Fetches financial data using the yfinance library.

  Args:
    ticker (str): The ticker symbol of the stock or asset.
    period (str): The time period for which to fetch the data. Can be '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', or 'max'.
    interval (str, optional): The time interval between data points. Can be '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', or '3mo'. Defaults to None.
    start (str, optional): The start date for the data in the format 'YYYY-MM-DD'. Defaults to None.
    end (str, optional): The end date for the data in the format 'YYYY-MM-DD'. Defaults to None.

  Returns:
    pandas.DataFrame: The fetched financial data.

  """

  if period != None:
    dataF = yf.download(tickers=ticker, interval=interval, period=period)
  else:
    dataF = yf.download(tickers=ticker, interval=interval, start=start, end=end)

  dataF.iloc[:, :]

  df = pd.DataFrame(dataF)

  # use df index, convert DateTime to a column instead of index
  df.reset_index(inplace=True)

  # delete Adj Close
  df = df.drop(["Adj Close"], axis=1)

  # rename Datetime to "Gmt time"
  df = df.rename(columns={"Datetime": "Gmt time"})

  # rename Date to "Gmt time"
  df = df.rename(columns={"Date": "Gmt time"})

  df["Gmt time"] = pd.to_datetime(df["Gmt time"], format="%d.%m.%Y %H:%M:%S")
  df.set_index("Gmt time", inplace=True)
  df = df[df.High != df.Low]

  return df
