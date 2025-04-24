from fastapi import APIRouter
from fastapi.responses import Response
from fastapi import Request
import requests
import os
import json
import logging

# Load environment variables from .env file
from dotenv import load_dotenv, find_dotenv

from app.ai.service import get_chatbot_response_async
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

    chatbot_message_raw = await get_chatbot_response_async(message_content, username)
    print("chatbot_message", chatbot_message_raw)
    chatbot_message = chatbot_message_raw["okaneChatBot"]["messages"][-1].content
    

    # Send response back to Discord
    url = os.environ.get("DISCORD_OKANE_AGENTS_CHANNEL_WEBHOOK_URL")
    headers = {
        "Content-Type": "application/json",
    }

    def smart_split(text, max_length=1900):
        chunks = []
        while len(text) > max_length:
            # Find a good breakpoint (after a paragraph or markdown element)
            cutoff = max_length
            
            # Check for suitable break points like line breaks or markdown elements
            breakpoints = [text.rfind('\n\n', 0, max_length), 
                          text.rfind('\n', 0, max_length),
                          text.rfind('. ', 0, max_length)]
            
            # If we're in the middle of a markdown link, find the end of the link
            if '[' in text[:cutoff] and '](' in text[:cutoff] and ')' in text:
                last_link_end = text[:cutoff].rfind(')')
                if last_link_end >= 0:
                    breakpoints.append(last_link_end + 1)

            # Choose the best breakpoint
            for point in breakpoints:
                if point > 0:
                    cutoff = point
                    break
                    
            # Add the chunk and continue with the rest
            chunks.append(text[:cutoff])
            text = text[cutoff:]
        
        # Add the remaining text as the final chunk
        chunks.append(text)
        return chunks

    if len(chatbot_message) > 2000:
        chunks = smart_split(chatbot_message)
        for chunk in chunks:
            payload = {"content": str(chunk)}
            if message_id != "": 
                payload["message_reference"] = {
                    "message_id": str(message_id)
                }
            print(payload)
            print("Sending Discord notification chunk...")
            requests.post(url, headers=headers, data=json.dumps(payload))
            print(f"Discord notification chunk sent successfully.")
    else:
        payload = {"content": str(chatbot_message)}
        if message_id != "": 
            payload["message_reference"] = {
                "message_id": str(message_id)
            }

        print(payload)
        print("Sending Discord notification...")
        requests.post(url, headers=headers, data=json.dumps(payload))
        print(f"Discord notification sent successfully.")
    return {"status": "Message processed"}