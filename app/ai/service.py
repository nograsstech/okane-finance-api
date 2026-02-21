from app.ai.chatbot import create_chatbot_graph, in_memory_store


async def get_chatbot_response_stream(user_input: str, thread_id: str = "User"):
    print("user_input is:", user_input)
    print("Calling with thread_id:", thread_id)
    # Create an async stream - don't await since it's an async generator
    stream = create_chatbot_graph().astream(
        {"messages": [("user", user_input)]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode=["messages", "values"],
    )

    # Iterate through the stream and yield each chunk
    async for chunk in stream:
        yield chunk


async def get_chatbot_response_async(user_input: str, thread_id: str = "User"):
    print("user_input is: ", user_input)
    print("Calling with thread_id: ", thread_id)
    events = await create_chatbot_graph().ainvoke(
        {"messages": [("user", user_input)]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="values",
    )
    # Properly await the async generator:
    # all_events = [event async for event in events]
    all_events = events
    for event in all_events:
        if isinstance(event, dict) and "messages" in event:
            event["messages"][-1].pretty_print()
    return {"okaneChatBot": all_events}  # Return all events


# async def get_chat_history(thread_id: str):
#     print("Getting chat history for thread_id:", thread_id)
#     namespace = ("memories", thread_id)
#     memories = in_memory_store.search(namespace)
#     messages = []
#     for memory in memories:
#         if isinstance(memory.value, dict) and "data" in memory.value:
#             messages.append(memory.value["data"])
#         else:
#             messages.append(memory.value)
#     return messages


async def get_chat_history(thread_id: str):
    """
    Retrieve chat history for a specific thread to match exactly
    the format expected by the frontend.
    """
    print("Getting chat history for thread_id:", thread_id)
    namespace = ("memories", thread_id)
    memories = in_memory_store.search(namespace)

    # Extract and format messages from memories
    conversation = []

    for memory in memories:
        if isinstance(memory.value, dict) and "data" in memory.value:
            data = memory.value["data"]

            # If data is already a dict with role/content, use it directly
            if isinstance(data, dict) and "role" in data and "content" in data:
                conversation.append(data)
            # If it's a string, determine if it's from user or assistant
            elif isinstance(data, str):
                # Alternate between user and assistant
                role = "user" if len(conversation) % 2 == 0 else "assistant"
                conversation.append({"role": role, "content": data})
            # Handle other potential formats
            else:
                # For other types, attempt to serialize
                from app.ai.router import serialize_message

                try:
                    serialized = serialize_message(data)
                    conversation.append(serialized)
                except(Exception) as e:
                    print(f"Error serializing data: {e}")
                    # Fallback
                    conversation.append({"role": "unknown", "content": str(data)})

    # Create a response in the exact same format as the streaming response
    final_content = {"role": "values", "content": {"messages": conversation}}

    return [final_content]  # Return as an array to match streaming format
