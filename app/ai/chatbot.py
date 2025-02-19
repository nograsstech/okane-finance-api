import json
import asyncio
from IPython.display import Image, display
from typing_extensions import TypedDict, Annotated
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from app.ai.models.gemini import gemini2Flash
from app.news.service import get_news_sentiment_per_period_by_ticker
from langchain_core.tools import Tool

# State

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


# Tools

tavilySearchTool = TavilySearchResults(max_results=2)

async def async_wrapper(**kwargs):
    ticker = kwargs.get("ticker")
    if not ticker:
        raise ValueError("Missing required argument: 'ticker'")
    print(1)
    return await get_news_sentiment_per_period_by_ticker(ticker)

news_sentiment_tool = Tool(
    name="get_news_sentiment",
    func=get_news_sentiment_per_period_by_ticker,  # Async function
    coroutine=get_news_sentiment_per_period_by_ticker,  # Required for async tools
    description="Fetches sentiment analysis for a given stock ticker over different time periods.",
)


tools = [tavilySearchTool, news_sentiment_tool]
tool_node = ToolNode(tools=tools)

class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""

    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    async def __call__(self, inputs: dict):
        if messages := inputs.get("messages", []):
            message = messages[-1]
        else:
            raise ValueError("No message found in input")

        outputs = []
        tasks = []

        for tool_call in message.tool_calls:
            tool = self.tools_by_name[tool_call["name"]]
            tool_args = tool_call["args"]

            if asyncio.iscoroutinefunction(tool.func):
                print(2)
                task = tool.ainvoke(tool_args)  # Ensure async execution
                tasks.append((task, tool_call))
            else:
                print(3)
                tool_result = tool.func(tool_args)  # Sync function
                outputs.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )

        # Await all async tool tasks
        for task, tool_call in tasks:
            print(4)
            tool_result = await task
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

        return {"messages": outputs}


def route_tools(
    state: State,
):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return END


tool_node = BasicToolNode(tools=tools)


# LLM

gemini2Flash_with_tools = gemini2Flash.bind_tools(tools)

# ChatBot

async def okaneChatBot(state: State):
    try:
        print(5)
        result = await gemini2Flash_with_tools.ainvoke(state["messages"])  # Ensure async execution
        return {"messages": [result]}
    except Exception as e:
        raise ValueError(f"Error in okaneChatBot: {e}")


# Memory 

memory = MemorySaver()
config = {"configurable": {"thread_id": "1"}}

# Graph

graph_builder = StateGraph(State)
graph_builder.add_edge(START, "okaneChatBot")
graph_builder.add_node("okaneChatBot", okaneChatBot)
graph_builder.add_conditional_edges(
    "okaneChatBot",
    route_tools,
    # The following dictionary lets you tell the graph to interpret the condition's outputs as a specific node
    # It defaults to the identity function, but if you
    # want to use a node named something else apart from "tools",
    # You can update the value of the dictionary to something else
    # e.g., "tools": "my_tools"
    {"tools": "tools", END: END},
)
graph_builder.add_node("tools", tool_node)
graph_builder.add_edge("okaneChatBot", END)
graph = graph_builder.compile()

def get_langgraph_graph():
    try:
        return graph.get_graph().draw_mermaid_png()
    except Exception:
        # This requires some extra dependencies and is optional
        return None