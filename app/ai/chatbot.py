import json
import asyncio
import uuid
from IPython.display import Image, display
from typing_extensions import TypedDict, Annotated

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

# Import our custom modules and tools
from app.ai.models.gemini import gemini2Flash, financial_advisor_chain
from app.ai.tools.news_sentiment import news_sentiment_tool
from app.ai.tools.get_yfinance_news import fetch_yfinance_news
from app.ai.sentiment_analyzer import analyze_sentiment
from app.ai.tools.duckduckgo_search import duckduckgo_search_tool

# Import and instantiate DuckDuckGoSearchRun
from langchain_community.tools import DuckDuckGoSearchRun
duckduckgo_search_tool = DuckDuckGoSearchRun()

# ---------------------------
# State
# ---------------------------
class State(TypedDict):
    # The "messages" key will accumulate messages (using add_messages for proper merging)
    messages: Annotated[list, add_messages]

# ---------------------------
# Tools
# ---------------------------
# List of tool instances; note that DuckDuckGoSearchRun is now instantiated.
tools = [duckduckgo_search_tool, news_sentiment_tool, fetch_yfinance_news]

class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""
    def __init__(self, tools: list) -> None:
        # Create a mapping from tool name to tool instance
        self.tools_by_name = {tool.name: tool for tool in tools}

    async def __call__(self, inputs: dict):
        messages = inputs.get("messages", [])
        if not messages:
            raise ValueError("No message found in input")
        message = messages[-1]

        outputs = []
        tasks = []

        # Iterate through each tool call in the message
        for tool_call in message.tool_calls:
            tool = self.tools_by_name[tool_call["name"]]
            tool_args = tool_call["args"]

            # Use the asynchronous method if available
            if hasattr(tool, "arun") and asyncio.iscoroutinefunction(tool.arun):
                task = tool.arun(tool_args)  # call the async method
                tasks.append((task, tool_call))
            # Fallback to the synchronous method if available
            elif hasattr(tool, "run"):
                tool_result = tool.run(tool_args)
                outputs.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )
            else:
                raise ValueError(f"Tool {tool_call['name']} does not have 'run' or 'arun' method.")

        # Await all asynchronous tasks and process results
        for task, tool_call in tasks:
            tool_result = await task
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

        return {"messages": outputs}

# ---------------------------
# Sentiment Analysis Agent
# ---------------------------
async def sentiment_analysis_agent(state: State):
    messages = state.get("messages", [])
    if len(messages) < 2:
        return {"messages": []}

    sentiment_data = None
    yfinance_news = None

    # Search for tool response messages by their tool names
    for message in messages:
        if hasattr(message, "name"):
            if message.name == "get_news_sentiment":
                sentiment_data = json.loads(message.content)
            elif message.name == "fetch_yfinance_news":
                yfinance_news = json.loads(message.content)

    # If both tool responses are available, run the sentiment analyzer
    if sentiment_data and yfinance_news:
        analysis = await analyze_sentiment({
            "sentiment_data": sentiment_data,
            "news": yfinance_news
        })
        return {"messages": [{"role": "assistant", "content": analysis}]}

    return {"messages": []}

# ---------------------------
# Routing Function for Tools
# ---------------------------
def route_tools(state: State):
    """
    Route to the "tools" node if the last message contains tool calls,
    otherwise, proceed to END.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state: {state}")

    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    else:
        return END

# ---------------------------
# LLM Agent Binding
# ---------------------------
# Bind the tools (including our DuckDuckGo search tool) to the LLM model
gemini2Flash_with_tools = gemini2Flash.bind_tools(tools)

# ---------------------------
# ChatBot Agent
# ---------------------------
async def okane_chat_agent(state: State, config: RunnableConfig, *, store: BaseStore):
    thread_id = config["configurable"]["thread_id"]
    namespace = ("memories", thread_id)
    memories = store.search(namespace, query=str(state["messages"][-1].content))
    info = "\n".join([d.value["data"] for d in memories])
    system_msg = (
        "You are a financial advisor. Please provide helpful and informative responses "
        "to the user's questions about finance. You have access to the following tools: "
        "DuckDuckGoSearchRun, news_sentiment_tool, fetch_yfinance_news. Here's some context: "
        f"{info}"
    )

    last_message = state["messages"][-1]
    if "remember" in last_message.content.lower():
        memory = last_message.content
        store.put(namespace, str(uuid.uuid4()), {"data": memory})

    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No message found in input")

    try:
        result = await gemini2Flash_with_tools.ainvoke(
            [{"role": "system", "content": system_msg}] + state["messages"]
        )
        return {"messages": [result]}
    except Exception as e:
        raise ValueError(f"Error in okane_chat_agent: {e}")

# ---------------------------
# Memory Setup
# ---------------------------
memory = MemorySaver()

from langgraph.store.memory import InMemoryStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

in_memory_store = InMemoryStore(
    index={
        "embed": GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    }
)

# ---------------------------
# Graph Construction
# ---------------------------
# Create the tool node using our list of tool instances
tool_node = BasicToolNode(tools=tools)

# Build the state graph
graph_builder = StateGraph(State)
graph_builder.add_edge(START, "okane_chat_agent")
graph_builder.add_node("okane_chat_agent", okane_chat_agent)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("sentiment_analysis_agent", sentiment_analysis_agent)

# Conditional routing: if the last AI message has tool calls, go to "tools"
graph_builder.add_conditional_edges(
    "okane_chat_agent",
    route_tools,
    {"tools": "tools", END: END},
)
graph_builder.add_edge("tools", "sentiment_analysis_agent")
graph_builder.add_edge("sentiment_analysis_agent", END)

# Compile the graph with checkpointing and persistent store
graph = graph_builder.compile(checkpointer=memory, store=in_memory_store)

def get_langgraph_graph():
    try:
        return graph.get_graph().draw_mermaid_png()
    except Exception:
        # Optional: this requires extra dependencies to render the diagram
        return None
