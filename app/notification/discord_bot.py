import discord
import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = "AiabNKyqqDB5xNCQJ3i8HglME_o_A-yS1NbyNSeclLSuVs6UxRd14iFqkOK_8y9sqGmv"
CHANNEL_ID = 1341847935154913302
WEBHOOK_URL = "https://0202-2405-9800-b660-c33c-74e4-d50e-4c3c-d6f8.ngrok-free.app/notification/discord-webhook"  # Your FastAPI endpoint

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:  # Ignore bot's own messages
        return
    if message.channel.id != CHANNEL_ID:  # Only forward messages from a specific channel
        return

    # Send the message to FastAPI
    data = {"user": message.author.name, "message": message.content}
    response = requests.post(WEBHOOK_URL, json=data)

    if response.status_code == 200:
        print(f"Sent message from {message.author.name} to FastAPI")
    else:
        print(f"Error forwarding message: {response.status_code}")

client.run(TOKEN)
