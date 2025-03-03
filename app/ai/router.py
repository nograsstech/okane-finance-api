from io import BytesIO
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.ai.chatbot import get_langgraph_graph
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ai.service import get_chatbot_response
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

@router.get("/chat")
async def get_chat():
  return 

def serialize_message(message):
    # Convert known message types (e.g. HumanMessage, AIMessage) into dicts.
    if hasattr(message, "role") and hasattr(message, "content"):
        return {"role": message.role, "content": message.content}
    # Fallback: simply use its string representation.
    return str(message)


@router.post("/chatbot-with-tool")
async def chatbot(request: MessageRequest):
    try:
        user_input = request.message
        thread_id = request.thread_id

        async def event_generator():
            async for event in get_chatbot_response(user_input=user_input, thread_id=thread_id):
                # Serialize the event before JSON dumping it
                serialized = serialize_message(event)
                yield f"{json.dumps(serialized)}"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
