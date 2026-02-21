import financedatabase as fd
import dotenv
import os

dotenv.load_dotenv()

equities = fd.Equities()

telecomunication_services = equities.search(
    industry="Diversified Telecommunication Services",
    country="United States",
    market_cap="Mega Cap",
    exclude_exchanges=True)

toolkit = telecomunication_services.to_toolkit(
    api_key=os.getenv("FINANCIAL_MODELING_PREP_KEY"),
    start_date="2000-01-01",
    progress_bar=False
)

# For example, obtain the historical data
historical_data = toolkit.get_historical_data()