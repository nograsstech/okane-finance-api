import discord
import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID"))
OKANE_FINANCE_API_URL = os.getenv("OKANE_FINANCE_API_URL")
WEBHOOK_URL = f"{OKANE_FINANCE_API_URL}/notification/discord-webhook"  # Your FastAPI endpoint

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
    print(message)
    try:
        data = {
            "user": message.author.name,
            "message": message.content,
            "message_id": message.id
        }
        response = requests.post(WEBHOOK_URL, json=data)
        response.raise_for_status()
        print(f"Sent message from {message.author.name} to FastAPI")
    except requests.exceptions.RequestException as e:
        print(f"Error forwarding message: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response content: {e.response}")


client.run(TOKEN)
