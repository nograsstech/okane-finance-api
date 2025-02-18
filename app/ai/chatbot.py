import json
from IPython.display import Image, display
from typing_extensions import TypedDict, Annotated
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from app.ai.models.gemini import gemini2Flash


# State

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


# Tools

tool = TavilySearchResults(max_results=2)
tools = [tool]
tool_node = ToolNode(tools=[tool])

class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""

    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    def __call__(self, inputs: dict):
        if messages := inputs.get("messages", []):
            message = messages[-1]
        else:
            raise ValueError("No message found in input")
        outputs = []
        for tool_call in message.tool_calls:
            tool_result = self.tools_by_name[tool_call["name"]].invoke(
                tool_call["args"]
            )
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


tool_node = BasicToolNode(tools=[tool])


# LLM

gemini2Flash_with_tools = gemini2Flash.bind_tools(tools)

# ChatBot

def okaneChatBot(state: State):
    return {"messages": [gemini2Flash_with_tools.invoke(state["messages"])]}

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
