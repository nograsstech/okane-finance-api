import os
import getpass
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables from .env file
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

# Ensure GOOGLE_API_KEY is set
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google AI API key: ")

geminiExp1206 = ChatGoogleGenerativeAI(
    model="gemini-exp-1206",
    temperature=0,
    max_tokens=1000,
    timeout=None,
    max_retries=4,
    # other params...
)


gemini2Flash = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0.4,
    max_tokens=None,
    timeout=None,
    max_retries=4,
    # other params...
)

