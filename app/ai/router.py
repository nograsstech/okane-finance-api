from io import BytesIO
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.ai.chatbot import get_langgraph_graph
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ai.service import get_chatbot_response

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


@router.post("/chatbot-with-tool")
async def chatbot(request: MessageRequest):
    try:
        user_input = request.message
        thread_id = request.thread_id
        return await get_chatbot_response(user_input=user_input, thread_id=thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))