from app.ai.chatbot import graph

async def get_chatbot_response(user_input: str, thread_id: str = "User"):
    print("user_input is:", user_input)
    print("Calling with thread_id:", thread_id)
    # Await the result (which is not an async generator)
    result = await graph.ainvoke(
        {"messages": [("user", user_input)]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="values"
    )
    # Yield the result as a single event
    yield result
