# Tech Context

## Technologies Used

*   **Programming Language:** Python 3.11 (specified in Dockerfile)
*   **Web Framework:** FastAPI
*   **API Server:** Uvicorn (with Gunicorn for production)
*   **Database:** MongoDB (accessed via `motor` for asynchronous operations)
*   **Financial Data Libraries:**
    *   yfinance
    *   pandas-ta
*   **Backtesting Library:** Backtesting.py
*   **AI/Chatbot Libraries:**
    *   Langchain
    *   Langchain-google-genai
    *   LangGraph
    * Google Generative AI (Gemini models)
*   **Notification Libraries:**
    *   `requests` (for sending HTTP requests to Discord/LINE webhooks)
    *   `discord.py`
* **Data Processing:**
    * pandas
    * numpy
*   **Other Libraries:**
    *   aiohttp (for asynchronous HTTP requests)
    *   python-dotenv (for environment variable management)
    *   loguru (for logging)
    *   zlib and base64 (for data compression/decompression)
    * Supabase (for storing backtesting results)
* **Containerization:** Docker
* **Cloud Deployment:** Google Cloud Run (implied by `build-push-deploy.sh` and `app.yaml`)

## Development Setup

1.  **Install Python:** Ensure Python 3.11 or a compatible version is installed.
2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    . venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set Environment Variables:** Create a `.env` file in the root directory and define the necessary environment variables:
    *   `MONGO_USER`
    *   `MONGO_PASSWORD`
    *   `ALPHA_VANTAGE_API_KEY`
    *   `GOOGLE_API_KEY`
    *   `DISCORD_BOT_TOKEN`
    *   `DISCORD_CHANNEL_ID`
    *   `DISCORD_OKANE_AGENTS_CHANNEL_WEBHOOK_URL`
    *   `OKANE_FINANCE_API_URL`
    *   `OKANE_SIGNALS_URL`
    *   `LINE_SECRET`
    *   `DISCORD_WEBHOOK_URL`
    *   `SUPABASE_URL`
    *   `SUPABASE_KEY`
    *  `OKANE_FINANCE_API_USER`
    *  `OKANE_FINANCE_API_PASSWORD`
    *   `ENV` (set to 'development' or 'production')

5.  **Run the Application (Development):**
    ```bash
    fastapi dev --host 127.0.0.1 --port 8001 app.main:app
    ```
6. **Run the Discord Bot:**
    ```bash
    python app/bots/discord_bot.py
    ```

## Technical Constraints

*   **Rate Limits:**  Third-party APIs (Alpha Vantage, Yahoo Finance, etc.) may have rate limits that need to be handled gracefully.
*   **Data Availability:** The availability and quality of data depend on the external data providers.
*   **Asynchronous Complexity:**  Managing asynchronous operations requires careful handling of concurrency and error handling.

## Dependencies

*   The `requirements.txt` file lists all project dependencies.
*   Dependency management is handled via `pip`.
*   No specific version conflicts are apparent from the provided `requirements.txt`, but compatibility should be monitored as dependencies are updated.