from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.ai.chatbot import graph, config, get_langgraph_graph
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

class MessageRequest(BaseModel):
    message: str

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
        events = graph.stream(
            {"messages": [("user", user_input)]}, config, stream_mode="values"
        )
        all_events = list(events)  # Collect all events
        for event in all_events:
            event["messages"][-1].pretty_print()
        return {"okaneChatBot": all_events}  # Return all events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))