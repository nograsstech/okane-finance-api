from io import BytesIO
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.ai.chatbot import get_langgraph_graph
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ai.service import get_chatbot_response_stream
from typing import List, Dict
from app.ai.service import get_chat_history

import json


class MessageRequest(BaseModel):
    message: str
    thread_id: str


router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    responses={404: {"description": "Not found"}},
)


@router.get("/graph")
async def get_graph():
    image_data = get_langgraph_graph()
    return StreamingResponse(BytesIO(image_data), media_type="image/png")


# Custom JSON encoder to handle LangChain message objects
class MessageEncoder(json.JSONEncoder):
    def default(self, obj):
        # Use the simplified serialization function for any object
        if hasattr(obj, "content") or (
            hasattr(obj, "__class__") and "Message" in obj.__class__.__name__
        ):
            return serialize_message(obj)
        # Let the base class handle other types or raise TypeError
        return json.JSONEncoder.default(self, obj)


router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    responses={404: {"description": "Not found"}},
)


def serialize_message(message):
    """
    Serialize different types of message objects into a consistent dictionary format.

    Args:
        message: The message object to serialize

    Returns:
        dict: A standardized message representation with 'role' and 'content'
    """
    # Handle dictionary format
    if isinstance(message, dict):
        if "role" in message and "content" in message:
            return message
        elif "content" in message:
            return {"role": "assistant", "content": message["content"]}

    # Handle class attributes - common pattern extraction
    role = "assistant"  # Default role
    content = ""

    # Try to determine the role based on class name
    class_name = message.__class__.__name__ if hasattr(message, "__class__") else ""
    if "HumanMessage" in class_name:
        role = "user"
    elif "SystemMessage" in class_name:
        role = "system"
    elif "AIMessage" in class_name:
        role = "assistant"

    # Try to find content attribute
    if hasattr(message, "content"):
        content = message.content
    else:
        content = str(message)

    # Override role from explicit attributes if available
    if hasattr(message, "type"):
        message_type = getattr(message, "type", "")
        if message_type == "human":
            role = "user"
        elif message_type == "system":
            role = "system"

    if hasattr(message, "role"):
        role = message.role

    # Handle tuple format (role, content)
    if isinstance(message, tuple) and len(message) == 2:
        return {"role": message[0], "content": message[1]}

    return {"role": role, "content": content}


@router.post("/chatbot-with-tool")
async def chatbot(request: MessageRequest):
    try:
        user_input = request.message
        thread_id = request.thread_id

        async def event_generator():
            # We'll accumulate messages as dictionaries in this list.
            messages_array = []

            async for event in get_chatbot_response_stream(
                user_input=user_input, thread_id=thread_id
            ):
                try:
                    # Serialize the message to a standard format
                    serialized = serialize_message(event)
                    messages_array.append(serialized)

                    # Create a JSON response where "content" is a regular JSON array
                    json_response = {
                        "status": "streaming",
                        "thread_id": thread_id,
                        "content": messages_array,
                    }

                    # Use our custom encoder to handle any special message objects
                    if json_response["content"][-1]["role"] == "values":
                        yield (
                            json.dumps(json_response, cls=MessageEncoder)
                            + "---END---\n"
                        )
                except TypeError as e:
                    print(f"Serialization error: {e}, type: {type(event)}")
                    # Add more diagnostic info
                    if hasattr(event, "__dict__"):
                        print(f"Object attributes: {event.__dict__}")

                    # Fallback using string representation
                    messages_array.append({"role": "assistant", "content": str(event)})
                    json_response = {
                        "status": "streaming",
                        "thread_id": thread_id,
                        "content": messages_array,
                    }
                    yield json.dumps(json_response) + "---END---\n"

            # Final completion message
            json_response = {
                "status": "complete",
                "thread_id": thread_id,
                "content": messages_array,
            }
            yield json.dumps(json_response, cls=MessageEncoder) + "---END---\n"

        return StreamingResponse(event_generator(), media_type="application/json")
    except Exception as e:
        print(f"Error in chatbot endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat")
async def get_chat(thread_id: str):
    try:
        messages: List[Dict] = await get_chat_history(thread_id=thread_id)

        # Format the response to match the streaming format for consistency
        response = {"status": "complete", "thread_id": thread_id, "content": messages}

        return JSONResponse(content=response)
    except Exception as e:
        print(f"Error in get_chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
