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

            [DO]
            Analyze and compare this sentiment data of the ticker using the provided data over different sentiment periods. Analyze the trend.
            Be detailed about each period and list them out clearly in bullet points.
            Analyze the news as additional context.
            Explain the trends clearly and concisely.
            Make financial recommendations.
            Separete the sentiment analysis and news analysis into separate sections.
            Clearly state whether to BUY, SELL, or HOLD the asset.
            Format and list the link to the news articles.
            Cite the source name very briefly for search results.

            [DO NOT]
            Do not explain anything I didn't ask for.
            Do not output just the raw data, but instead, summarize the key points from the sentiment and news
            Do not explain the financial risk as I have already understand them. 
            Do not generate more than 1900 characters.
            Do not wrap the response in "```"

            <news>
            {json.dumps(sentiment_data.get("news"))}
            </news>

            <sentiment_data>
            {json.dumps(sentiment_data.get("sentiment_data"))}
            </sentiment_data>
            
            <search_results>
            {json.dumps(sentiment_data.get("search_results"))}
            </search_results>

            Use the news data to provide additional context for the sentiment analysis.
            """
    messages = [{"role": "user", "content": prompt}]
    result = await gemini2Flash.ainvoke(messages)
    return result.content
