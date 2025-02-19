from app.ai.models.gemini import gemini2Flash
import json

async def analyze_sentiment(sentiment_data):
    prompt = f"""
The overall sentiment score from Alpha Vantage typically ranges from -1 to 1. This scoring system is designed to quantify the sentiment expressed in qualitative data, such as financial news or social media comments, providing a clear indication of market sentiment.

Sentiment Score Range and Interpretation
-1: Represents the highest level of negative sentiment. This indicates strong disapproval or pessimism regarding the subject matter.

0: Indicates a neutral sentiment, suggesting that the opinions are balanced between positive and negative or that there is no significant emotional charge.

1: Denotes the highest level of positive sentiment, reflecting strong approval or optimism about the subject matter.

Meaning of Scores
Negative Scores (-1 to 0): Suggest a general trend of negativity or concern among respondents. For example, a score of -0.5 would indicate a moderate level of negative sentiment.

Neutral Scores (around 0): Imply that the sentiment is neither positive nor negative, which can occur when opinions are mixed or when there is a lack of strong feelings about the subject.

Positive Scores (0 to 1): Indicate approval and optimism. A score of 0.7 would suggest a strong positive sentiment.


Analyze this sentiment data of LMT using the provided data. Explain the trends clearly and concisely. Do not explain anything I didn't ask for. Make financial recommendations. Don't explain the financial risk as I have already understand them. 

< news_sentiment_tool  output here >

{json.dumps(sentiment_data)}
"""
    messages = [{"role": "user", "content": prompt}]
    result = await gemini2Flash.ainvoke(messages)
    return result.content
