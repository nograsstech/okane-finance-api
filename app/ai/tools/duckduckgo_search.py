from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import Tool

'''Tool for performing Tavily searches.'''
duckduckgo_search_tool = DuckDuckGoSearchRun()
