from langchain_community.tools.tavily_search import TavilySearchResults

'''Tool for performing Tavily searches.'''
tavilySearchTool = TavilySearchResults(max_results=2)
