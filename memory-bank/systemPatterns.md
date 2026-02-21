## System Architecture

The system adopts a microservices-oriented architecture, with separate components responsible for different functionalities. This allows for independent scaling and development of each service. The core components include:

1.  **API Gateway (FastAPI):** Handles incoming requests, authentication, and routing to appropriate services.
2.  **News Service:** Fetches and processes news data, performs sentiment analysis.
3.  **Ticker Service:** Retrieves and manages ticker information and historical price data.
4.  **Signals Service:** Calculates technical indicators and generates trading signals.
    The **Signals Service** is responsible for generating trading signals and performing backtests. It consists of the following sub-components:
    - **API Endpoints (router.py):** Defines the API endpoints for accessing signals and running backtests.
    - **Service Layer (service.py):** Contains the core logic for retrieving signals, performing backtests, and interacting with the database.
    - **Data Transfer Objects (dto.py):** Defines the data structures used for requests and responses.
    - **Signal Generators (signals_generator/):** Contains the logic for generating trading signals based on different technical indicators (e.g., EMA, MACD, RSI).
    - **Trading Strategies (strategies/):** Implements different trading strategies that use the generated signals to make buy and sell decisions.
    - **Backtesting (strategies/*_backtest.py):** Provides the functionality to backtest the trading strategies on historical data.
5.  **AI Service:** Provides the chatbot functionality and AI-driven insights.
6.  **Notification Service:** Manages sending notifications to users (Discord, LINE).
7.  **Database (MongoDB):** Stores historical data, news, sentiment scores, backtesting results, and trade actions.
8. **Bots (Discord):** Interact with users on Discord.

## Key Technical Decisions

*   **FastAPI:** Chosen for its high performance, ease of use, and automatic data validation capabilities.
*   **Python:**  Selected as the primary programming language due to its extensive libraries for data analysis, finance, and machine learning (pandas, yfinance, pandas-ta, Langchain, Backtesting.py).
*   **MongoDB:** Used as the database due to its flexible schema, scalability, and suitability for storing time-series data.
*   **Asynchronous Operations:**  Utilized extensively (async/await) to improve performance and handle concurrent requests.
* **Docker:** Used for containerization to ensure consistent deployment across different environments.
* **LangGraph:** Used for building the chatbot and managing conversation flow.
* **Google Gemini:** Used as the LLM for the chatbot.

**Rationale:**

*   The combination of FastAPI and Python provides a robust and efficient platform for building a financial API.
*   MongoDB's flexibility is well-suited for handling the diverse data types involved (news, prices, indicators).
*   Asynchronous operations are crucial for handling real-time data and preventing blocking operations.

## Design Patterns

*   **Strategy Pattern:** Used in the `signals` service to allow for easy implementation and switching between different trading strategies (EMA, MACD, Bollinger Bands, etc.). Each strategy is encapsulated in its own class.
*   **Observer Pattern:** Could be implemented for real-time updates (e.g., notifying users of new signals).  The `notification` service could act as an observer.
* **Factory Pattern:** Could be used for creating instances of different data fetching classes (e.g., AlphaVantage, YFinance).
* **Singleton Pattern:** Used for database connection (potentially).

## Component Relationships

*   The API Gateway receives requests and routes them to the appropriate service.
*   The `news` and `ticker` services fetch data from external APIs and store it in MongoDB.
*   The `signals` service retrieves data from MongoDB, calculates indicators, generates signals, and interacts with the `notification` service.
*   The `AI` service interacts with the user via the API Gateway and potentially uses data from other services (e.g., news sentiment).
*   The `notification` service sends messages to users via external platforms (Discord, LINE).
* The `bots` service interacts with the `notification` service to process messages.
