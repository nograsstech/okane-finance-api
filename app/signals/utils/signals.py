from starlette.status import HTTP_200_OK
import json


def get_latest_signal(signals_df):
    signals_df = signals_df.loc[signals_df['TotalSignal'] != 0]
    signals_df = signals_df.reset_index().rename(columns={'index':'Gmt time'})
    signals_df['gmtTime'] = signals_df['Gmt time'].astype(str)
    current_signal = signals_df.iloc[-1]
    current_signal = json.loads(current_signal.to_json())

    return current_signal

def get_all_signals(signals_df):
    # filter out rows where Total_Signal is not 0
    signals_df = signals_df.loc[signals_df['TotalSignal'] != 0]
    signals_df = signals_df.reset_index().rename(columns={'index':'Gmt time'})
    signals_df['gmtTime'] = signals_df['Gmt time'].astype(str)
    # convert the signals dataframe to a list of dictionaries
    signals_df = signals_df.fillna(0)  # replace NaN values with 0
    signals = signals_df.to_dict(orient='records')
    return signals
