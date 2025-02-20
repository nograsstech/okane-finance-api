from fastapi import APIRouter
from fastapi.responses import Response
from fastapi import Request
import requests
import os
import json
import logging

# Load environment variables from .env file
from dotenv import load_dotenv, find_dotenv

from app.ai.service import get_chatbot_response
load_dotenv(find_dotenv(), override=True)

router = APIRouter(
  prefix="/notification",
  tags=["ai"],
  responses={404: {"description": "Not found"}},
)

@router.get("/discord-webhook")
async def test_discord_webhook(request: Request):
    return {"status": "Discord Webhook Online"}

@router.post("/discord-webhook")
async def receive_discord_message(request: Request):
    data = await request.json()

    # Extract username and message content
    username = data.get("user", "")
    message_content = data.get("message", "")
    message_id = data.get("message_id", "")
    
    if (username == "Okane Agents"):
        return {"status": "Message processed"}

    chatbot_message_raw = await get_chatbot_response(message_content, username)
    print("chatbot_message", chatbot_message_raw)
    chatbot_message = chatbot_message_raw["okaneChatBot"]["messages"][-1].content
    

    # Send response back to Discord
    payload = {"content": str(chatbot_message)}
    
    if (message_id is not ""): 
        payload["message_reference"] = {
            "message_id":str( message_id)
        }

    print( payload )
    print("Sending Discord notification...", chatbot_message)
    url = os.environ.get("DISCORD_OKANE_AGENTS_CHANNEL_WEBHOOK_URL")
    headers = {
        "Content-Type": "application/json",
    }
    data = {"content": chatbot_message}
    requests.post(url, headers=headers, data=json.dumps(payload))
    print(f"Discord notification sent successfully.")
    return {"status": "Message processed"}