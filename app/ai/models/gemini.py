import os
import getpass
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import chain

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

financial_advisor_prompt = PromptTemplate.from_template(
    """You are a financial advisor. Please provide helpful and informative responses to the user's questions about finance.
    
    {input}"""
)



gemini2Flash = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0.6,
    max_tokens=None,
    timeout=None,
    max_retries=4,
    # other params...
)

gemini2FlashDiscordResponder = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0.6,
    max_tokens=1500,
    timeout=None,
    max_retries=4,
    # other params...
)

gemini2FlashLowTemperature = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-001",
    temperature=0.3,
    max_tokens=None,
    timeout=None,
    max_retries=4,  
)

financial_advisor_chain = financial_advisor_prompt | gemini2FlashLowTemperature