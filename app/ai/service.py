from langchain_core.messages import ToolMessage
from app.ai.chatbot import graph, get_langgraph_graph

async def get_chatbot_response(user_input: str, thread_id: str = "User"):
  print("user_input is: ", user_input)
  print("Calling with thread_id: ", thread_id)
  events = await graph.ainvoke(
      {"messages": [("user", user_input)]},
      config={"configurable": {"thread_id": thread_id }},
      stream_mode="values"
  )
  # Properly await the async generator:
  # all_events = [event async for event in events]
  all_events = events
  for event in all_events:
      if isinstance(event, dict) and "messages" in event:
          event["messages"][-1].pretty_print()
  return {"okaneChatBot": all_events}  # Return all events