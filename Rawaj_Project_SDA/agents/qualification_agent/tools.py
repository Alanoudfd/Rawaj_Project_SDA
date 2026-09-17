import os

from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain_core.tools import tool


load_dotenv()


web_search = TavilySearch(
    max_results=5,
    topic="general",
    search_depth="advanced",
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
)


@tool
def search_instagram_benchmark(query: str) -> str:
    """
    Search the web for current Instagram marketing benchmarks,
    especially for restaurants and food & beverage businesses.
    """

    results = web_search.invoke({
        "query": query
    })

    return str(results)