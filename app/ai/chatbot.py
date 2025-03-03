import json
import asyncio
import uuid
from IPython.display import Image, display
from typing_extensions import TypedDict, Annotated

from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
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
                task = tool.arun(tool_args)
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
# Grounding Agent
# ---------------------------
async def search_grounding_agent(state: State):
    """
    This node grounds the final answer by performing a DuckDuckGo search
    using the original user query (assumed to be the first message).
    """
    if not state.get("messages"):
        raise ValueError("No messages found in state for grounding.")

    # Use the original user query (first message) as the search query.
    # We assume the first message is a HumanMessage with a 'content' attribute.
    user_query = state["messages"][0].content if hasattr(state["messages"][0], "content") else ""
    search_args = {"query": user_query}

    # Run the search tool asynchronously.
    results = await duckduckgo_search_tool.arun(search_args)
    
    # Format the top 3 results (adjust formatting as needed)
    if isinstance(results, list):
        formatted_results = "\n".join(results[:3])
    else:
        formatted_results = str(results)
        
    grounding_message = AIMessage(content=f"Grounded search results:\n{formatted_results}")
    state["messages"].append(grounding_message)
    return state

# ---------------------------
# Sentiment Analysis Agent
# ---------------------------
async def sentiment_analysis_agent(state: State):
    messages = state.get("messages", [])
    if len(messages) < 2:
        return {"messages": []}

    sentiment_data = None
    yfinance_news = None
    search_results = None

    # Search for tool response messages by their tool names.
    for message in messages:
        if hasattr(message, "name"):
            if message.name == "get_news_sentiment":
                sentiment_data = json.loads(message.content)
            elif message.name == "fetch_yfinance_news":
                yfinance_news = json.loads(message.content)
            elif message.name == "DuckDuckGoSearchRun":
                search_results = json.loads(message.content)

    # If both tool responses are available, run the sentiment analyzer.
    if sentiment_data and yfinance_news:
        analysis = await analyze_sentiment({
            "sentiment_data": sentiment_data,
            "news": yfinance_news,
            "search_results": search_results
        })
        return {"messages": [AIMessage(content=analysis)]}

    return {"messages": []}

# ---------------------------
# Routing Function for Tools
# ---------------------------
def route_tools(state: State):
    """
    If the last AI message contains tool calls, route to the "tools" node;
    otherwise, continue to the grounding step.
    """
    messages = state.get("messages", [])
    if not messages:
        raise ValueError(f"No messages found in input state: {state}")
    ai_message = messages[-1]

    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    else:
        return "grounding_agent"

# ---------------------------
# LLM Agent Binding
# ---------------------------
# Bind the tools (including our DuckDuckGo search tool) to the LLM model.
gemini2Flash_with_tools = gemini2Flash.bind_tools(tools)

# ---------------------------
# ChatBot Agent
# ---------------------------
async def okane_chat_agent(state: State, config: RunnableConfig, *, store: BaseStore):
    thread_id = config["configurable"]["thread_id"]
    namespace = ("memories", thread_id)
    # Use attribute access for the message content
    memories = store.search(namespace, query=state["messages"][-1].content)
    info = "\n".join([d.value["data"] for d in memories])
    system_msg = (
        "You are a financial advisor. Please provide helpful and informative responses "
        "to the user's questions about finance. You have access to the following tools: "
        "DuckDuckGoSearchRun, news_sentiment_tool, fetch_yfinance_news. Here's some context: "
        f"{info}"
    )

    last_message = state["messages"][-1]
    if "remember" in last_message.content.lower():
        store.put(namespace, str(uuid.uuid4()), {"data": last_message.content})

    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No message found in input")

    try:
        # Combine the system message with existing messages.
        # Adjust the format if needed for your LLM.
        result = await gemini2Flash_with_tools.ainvoke(
            [{"role": "system", "content": system_msg}] + messages
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
# Create the tool node using our list of tool instances.
tool_node = BasicToolNode(tools=tools)

graph_builder = StateGraph(State)
graph_builder.add_edge(START, "okane_chat_agent")
graph_builder.add_node("okane_chat_agent", okane_chat_agent)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("grounding_agent", search_grounding_agent)
graph_builder.add_node("sentiment_analysis_agent", sentiment_analysis_agent)

# Conditional routing: if tool calls exist, run the "tools" node; otherwise, jump to grounding.
graph_builder.add_conditional_edges(
    "okane_chat_agent",
    route_tools,
    {"tools": "tools", "grounding_agent": "grounding_agent"},
)
# If the "tools" node was executed, continue to grounding.
graph_builder.add_edge("tools", "grounding_agent")
# After grounding, run sentiment analysis (if applicable) before ending.
graph_builder.add_edge("grounding_agent", "sentiment_analysis_agent")
graph_builder.add_edge("sentiment_analysis_agent", END)

# Compile the graph with checkpointing and persistent store.
graph = graph_builder.compile(checkpointer=memory, store=in_memory_store)

def get_langgraph_graph():
    try:
        return graph.get_graph().draw_mermaid_png()
    except Exception:
        # Optional: rendering the diagram requires extra dependencies.
        return None
