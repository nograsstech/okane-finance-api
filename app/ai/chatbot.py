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
from app.ai.models.gemini import create_gemini_flash_model # Import the function
from app.ai.tools.news_sentiment import news_sentiment_tool
from app.ai.tools.get_yfinance_news import fetch_yfinance_news
from app.ai.sentiment_analyzer import analyze_sentiment # analyze_sentiment now accepts LLM
from langchain_core.language_models import BaseChatModel # Import for type hinting

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
            
            # Ensure tool_call_id is present and properly set
            tool_call_id = tool_call.get("id")
            if not tool_call_id:
                # Generate a UUID if id not present
                tool_call_id = str(uuid.uuid4())

            # Use the asynchronous method if available
            if hasattr(tool, "arun") and asyncio.iscoroutinefunction(tool.arun):
                task = tool.arun(tool_args)  # call the async method
                tasks.append((task, tool_call, tool_call_id))
            # Fallback to the synchronous method if available
            elif hasattr(tool, "run"):
                tool_result = tool.run(tool_args)
                outputs.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call_id,
                    )
                )
            else:
                raise ValueError(f"Tool {tool_call['name']} does not have 'run' or 'arun' method.")

        print(f"tool_call in sync: {tool_call}")
        print(f"tool_call.keys() in sync: {tool_call.keys()}")
        print(f"tool_call.get('id') in sync: {tool_call.get('id')}")
        print(f"tool_call.get('name') in sync: {tool_call.get('name')}")
        print(f"tool_call.get('args') in sync: {tool_call.get('args')}")

        # Await all asynchronous tasks and process results
        for task, tool_call, tool_call_id in tasks:
            print(f"tool_call in async: {tool_call}")
            print(f"tool_call.keys() in async: {tool_call.keys()}")
            print(f"tool_call.get('id') in async: {tool_call.get('id')}")
            print(f"tool_call.get('name') in async: {tool_call.get('name')}")
            print(f"tool_call.get('args') in async: {tool_call.get('args')}")
            tool_result = await task
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call_id,
                )
            )

        return {"messages": outputs}
# ---------------------------
# Grounding Agent
# ---------------------------
async def search_grounding_agent(state: State):
    """
    This node acts as a passthrough after tool execution, allowing the
    format_final_response agent to process the accumulated messages,
    including any DuckDuckGoSearchRun results added by the tools node.
    """
    # Simply return the current state's messages. The actual search was
    # performed by the tools node if the LLM decided to use DuckDuckGoSearchRun.
    messages = state.get("messages", [])
    return {"messages": messages}

# ---------------------------
# Sentiment Analysis Agent
# ---------------------------
async def sentiment_analysis_agent(state: State, llm: BaseChatModel):
    """
    Sentiment analysis agent that uses the LLM to analyze sentiment based on tool results.
    Accepts the LLM instance as an argument.
    """
    messages = state.get("messages", [])
    # Allow processing even with fewer than 2 messages if needed,
    # but the analysis function itself might handle missing data.
    # if len(messages) < 2:
    #     return {"messages": messages} # Preserve message history

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
        # Pass the LLM instance to the analyze_sentiment function
        analysis = await analyze_sentiment({
            "sentiment_data": sentiment_data,
            "news": yfinance_news,
            "search_results": search_results
        }, llm=llm)
        return {"messages": [AIMessage(content=analysis)]}

    return {"messages": messages} # Preserve message history

# ---------------------------
# Routing Function for Tools
# ---------------------------
# Routing Function for Sentiment Analysis
# ---------------------------
def check_sentiment_data_route(state: State):
    """
    Checks if sentiment analysis data is available in the state.
    Routes to sentiment_analysis_agent if data is present, otherwise to format_final_response.
    """
    messages = state.get("messages", [])
    sentiment_data_present = any(hasattr(msg, "name") and msg.name == "get_news_sentiment" for msg in messages)
    yfinance_news_present = any(hasattr(msg, "name") and msg.name == "fetch_yfinance_news" for msg in messages)

    if sentiment_data_present and yfinance_news_present:
        return "sentiment_analysis_agent"
    else:
        return "format_final_response"

# ---------------------------
# Final Response Formatting Agent
# ---------------------------
async def format_final_response(state: State):
    """
    Formats the final response based on the available information in the state.
    Includes original query, grounding results, and optional sentiment analysis.
    """
    messages = state.get("messages", [])
    user_query = ""
    sentiment_analysis_content = ""
    grounding_results_content = ""

    # Find the last HumanMessage (current query)
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    # Find the sentiment analysis result (look for AIMessage with specific content pattern)
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and "**Sentiment Analysis:**" in msg.content:
            sentiment_analysis_content = msg.content
            break

    # Find grounding results (look for ToolMessage from DuckDuckGoSearchRun)
    # Always look for grounding results (ToolMessage from DuckDuckGoSearchRun)
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == "DuckDuckGoSearchRun":
            try:
                search_content = json.loads(msg.content)
                if isinstance(search_content, list):
                    # Format search results to include source if available
                    formatted_search_results = []
                    for i, result in enumerate(search_content[:5]): # Limit to top 5 for brevity
                        if isinstance(result, dict) and 'title' in result and 'link' in result:
                             formatted_search_results.append(f"{i+1}. [{result['title']}]({result['link']})")
                        else:
                             formatted_search_results.append(f"{i+1}. {str(result)}") # Fallback formatting
                    grounding_results_content = "Search Results:\n" + "\n".join(formatted_search_results)
                else:
                    grounding_results_content = "Search Results:\n" + str(search_content)
            except:
                pass # Ignore if tool content is not JSON
            break # Take the most recent search results


    response_content = f"Regarding your query: '{user_query}'\n\n"

    # Include both sentiment analysis and grounding results if available
    if sentiment_analysis_content:
        response_content += sentiment_analysis_content
        if grounding_results_content:
            response_content += "\n\n" + grounding_results_content # Add grounding results below sentiment analysis
    elif grounding_results_content:
        response_content += "Could not perform sentiment analysis based on the available information, but here are some search results:\n\n"
        response_content += grounding_results_content
    else:
        response_content += "Could not find relevant information or perform analysis."


    return {"messages": [AIMessage(content=response_content)]}
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

    # This function will now route based on whether the AI message has tool calls.
    # The actual routing logic in the graph will use this function.
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "continue_tool_flow" # Route to the tool execution path
    else:
        return "end_chat" # Route directly to the end

# ---------------------------
# LLM Agent Binding
# ---------------------------
# Remove global LLM binding
# gemini2Flash_with_tools = gemini2Flash.bind_tools(tools)

# ---------------------------
# ChatBot Agent
# ---------------------------
async def okane_chat_agent(state: State, config: RunnableConfig, *, store: BaseStore, llm: BaseChatModel):
    """
    Chatbot agent that uses the LLM to generate responses, potentially calling tools.
    Accepts the LLM instance as an argument.
    """
    thread_id = config["configurable"]["thread_id"]
    namespace = ("memories", thread_id)
    # Use attribute access for the message content
    memories = store.search(namespace, query=state["messages"][-1].content)
    info = "\\n".join([d.value["data"] for d in memories])
    
    # Extract grounded search results from the state
    grounding_message = ""
    for msg in state["messages"]:
        # Look for the ToolMessage from DuckDuckGoSearchRun
        if isinstance(msg, ToolMessage) and msg.name == "DuckDuckGoSearchRun":
             try:
                 search_content = json.loads(msg.content)
                 if isinstance(search_content, list):
                     grounding_message = "Search Results:\n" + "\n".join(search_content[:3])
                 else:
                     grounding_message = "Search Results:\n" + str(search_content)
             except:
                 pass # Ignore if tool content is not JSON
             break # Take the most recent search results
            
    system_msg = (
        "You are a financial advisor. Please provide helpful and informative responses "
        "to the user's questions about finance. You have access to the following tools: "
        "DuckDuckGoSearchRun (excellent for general financial information and news), "
        "news_sentiment_tool (for analyzing sentiment of financial news), and "
        "fetch_yfinance_news (for fetching specific news from Yahoo Finance). "
        "Prioritize using these tools, especially DuckDuckGoSearchRun and fetch_yfinance_news, "
        "when the user asks for news, sentiment, or general information about financial topics or specific tickers. "
        "Here's some context: "
        f"{info}\\n{grounding_message}" # Incorporate grounding results
    )

    last_message = state["messages"][-1]
    store.put(namespace, str(uuid.uuid4()), {"data": last_message.content})
    if "remember" in last_message.content.lower():
        pass # previously stored the message here, now storing all messages

    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No message found in input")

    try:
        # Ensure we don't send empty messages to the Gemini model
        formatted_messages = [{"role": "system", "content": system_msg}]
        
        for msg in messages:
            # Skip any message with empty content
            if not hasattr(msg, 'content') or not msg.content:
                continue
                
            # Determine the role based on message type
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, ToolMessage):
                role = "tool"
                # For ToolMessages, we need to ensure we properly format them
                tool_message = {
                    "role": role,
                    "content": msg.content,
                    "name": getattr(msg, "name", "unknown_tool")
                }
                
                # Only include tool_call_id if it exists to avoid KeyError
                if hasattr(msg, "tool_call_id") and msg.tool_call_id is not None:
                    tool_message["tool_call_id"] = msg.tool_call_id
                
                formatted_messages.append(tool_message)
                continue  # Skip the default append below
            else:
                role = "user"  # Default fallback
                
            formatted_messages.append({"role": role, "content": msg.content})
        
        # Ensure we have at least one non-system message
        if len(formatted_messages) <= 1:
            # Add a fallback message if we somehow ended up with only the system message
            formatted_messages.append({"role": "user", "content": "Tell me about financial advice."})
            
        # Bind tools to the passed LLM instance
        llm_with_tools = llm.bind_tools(tools)
        result = await llm_with_tools.ainvoke(formatted_messages)
        store.put(namespace, str(uuid.uuid4()), {"data": result.content}) # Store the response
        return {"messages": [result]}
    except Exception as e:
        print(f"Error details in okane_chat_agent: {type(e)}, {str(e)}")
        # Add more detailed error handling/logging here
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

# Remove global graph instance
# graph = graph_builder.compile(checkpointer=memory, store=in_memory_store)

def create_chatbot_graph(llm: BaseChatModel):
    """
    Creates and compiles the LangGraph chatbot graph with the specified LLM instance.
    """
    # Create the tool node using our list of tool instances.
    tool_node = BasicToolNode(tools=tools)

    graph_builder = StateGraph(State)
    graph_builder.add_edge(START, "okane_chat_agent")

    # Define wrapper functions to pass the LLM and await the agents
    async def okane_chat_node(state: State, config: RunnableConfig, *, store: BaseStore):
        return await okane_chat_agent(state, config, store=store, llm=llm)

    async def sentiment_analysis_node(state: State):
        return await sentiment_analysis_agent(state, llm=llm)

    # Add nodes using the wrapper functions
    graph_builder.add_node("okane_chat_agent", okane_chat_node)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("grounding_agent", search_grounding_agent) # This agent is already async and passed directly
    graph_builder.add_node("sentiment_analysis_agent", sentiment_analysis_node)
    graph_builder.add_node("format_final_response", format_final_response) # This agent is already async and passed directly

    # Conditional routing: if tool calls exist, run the "tools" node; otherwise, jump to grounding.
    # Conditional routing after okane_chat_agent: check for tool calls
    # If tool calls exist, route to the tool execution path ("continue_tool_flow")
    # If no tool calls, route directly to END ("end_chat")
    graph_builder.add_conditional_edges(
        "okane_chat_agent",
        route_tools, # Use the modified route_tools function
        {
            "continue_tool_flow": "tools", # Route to tools if tool calls are present
            "end_chat": END # Route directly to END if no tool calls
        }
    )

    # The tool execution path: tools -> grounding_agent -> (sentiment_analysis_agent or format_final_response) -> format_final_response -> END
    graph_builder.add_edge("tools", "grounding_agent")

    # Conditional routing after grounding: check for sentiment data
    graph_builder.add_conditional_edges(
        "grounding_agent",
        check_sentiment_data_route,
        {
            "sentiment_analysis_agent": "sentiment_analysis_agent",
            "format_final_response": "format_final_response",
        },
    )

    # Direct edge from sentiment_analysis_agent to format_final_response
    graph_builder.add_edge("sentiment_analysis_agent", "format_final_response")

    # Direct edge from format_final_response to END
    graph_builder.add_edge("format_final_response", END)

    # Compile the graph with checkpointing and persistent store.
    # Use the global memory and in_memory_store instances
    compiled_graph = graph_builder.compile(checkpointer=memory, store=in_memory_store)

    return compiled_graph

# The graph is now created and compiled in create_chatbot_graph, not globally.
# The get_langgraph_graph function might need adjustment if it was used elsewhere
# to get the compiled graph instance. For now, keep it as is, but note it
# won't return a globally compiled graph anymore.
def get_langgraph_graph():
    try:
        # This function might need to be updated to accept the compiled graph
        # or the LLM to create it. Leaving as is for now, assuming it might
        # not be critical or will be updated elsewhere.
        return create_chatbot_graph().get_graph().draw_mermaid_png()
    except Exception:
        # Optional: rendering the diagram requires extra dependencies.
        return None
