from operator import itemgetter
from typing import Dict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import Runnable, RunnablePassthrough, RunnableLambda
from langchain.schema.runnable.config import RunnableConfig
from langchain.memory import ConversationBufferMemory
from chainlit.types import ThreadDict
from chainlit.input_widget import Select, Switch, Slider

import chainlit as cl


async def setup_runnable(settings):
    memory = cl.user_session.get("memory")

    gemini_model = settings.get("Gemini_Model", "gemini-2.0-flash")
    gemini_temperature = settings.get("Gemini_Temperature", 1)

    model = ChatGoogleGenerativeAI(
        model=gemini_model, temperature=gemini_temperature, streaming=True
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful chatbot"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )

    runnable = (
        RunnablePassthrough.assign(
            history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
        )
        | prompt
        | model
        | StrOutputParser()
    )
    cl.user_session.set("runnable", runnable)


@cl.password_auth_callback
def auth():
    return cl.User(identifier="test")


@cl.oauth_callback
def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: Dict[str, str],
    default_user: cl.User,
) -> Optional[cl.User]:
    return default_user


@cl.on_chat_start
async def on_chat_start():
    settings = await cl.ChatSettings(
        [
            Select(
                id="Gemini_Model",
                label="Google Gemini - Model",
                values=[
                    "gemini-2.0-flash-lite",
                    "gemini-2.0-flash",
                    "gemini-2.0-flash-exp",
                    "gemini-2.5-flash-preview-04-17",
                    "gemini-2.5-pro-preview-03-25",
                ],
                initial_index=1,
            ),
            Slider(
                id="Gemini_Temperature",
                label="Google Gemini - Temperature",
                initial=1,
                min=0,
                max=2,
                step=0.1,
            ),
            Slider(
                id="SAI_Steps",
                label="Stability AI - Steps",
                initial=30,
                min=10,
                max=150,
                step=1,
                description="Amount of inference steps performed on image generation.",
            ),
            Slider(
                id="SAI_Cfg_Scale",
                label="Stability AI - Cfg_Scale",
                initial=7,
                min=1,
                max=35,
                step=0.1,
                description="Influences how strongly your generation is guided to match your prompt.",
            ),
            Slider(
                id="SAI_Width",
                label="Stability AI - Image Width",
                initial=512,
                min=256,
                max=2048,
                step=64,
                tooltip="Measured in pixels",
            ),
            Slider(
                id="SAI_Height",
                label="Stability AI - Image Height",
                initial=512,
                min=256,
                max=2048,
                step=64,
                tooltip="Measured in pixels",
            ),
        ]
    ).send()

    cl.user_session.set("memory", ConversationBufferMemory(return_messages=True))
    await setup_runnable(settings)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    memory = ConversationBufferMemory(return_messages=True)
    root_messages = [m for m in thread["steps"] if m["parentId"] is None]
    for message in root_messages:
        if message["type"] == "user_message":
            memory.chat_memory.add_user_message(message["output"])
        else:
            memory.chat_memory.add_ai_message(message["output"])

    cl.user_session.set("memory", memory)

    settings = cl.user_session.get("settings")  # Retrieve settings from session
    
    print("\nSettings:", settings, "\n")
    
    if settings is None:
        # Initialize with default settings if not found in session
        settings = {
            "Gemini_Model": "gemini-2.0-flash",
            "Gemini_Temperature": 1,
            "SAI_Steps": 30,
            "SAI_Cfg_Scale": 7,
            "SAI_Width": 512,
            "SAI_Height": 512,
        }
    await setup_runnable(settings)


@cl.on_message
async def on_message(message: cl.Message):
    memory = cl.user_session.get("memory")

    runnable = cl.user_session.get("runnable")

    if not message.content.strip():
        await message.reply("Please provide a valid question.")
        return

    res = cl.Message(content="")

    async for chunk in runnable.astream(
        {"question": message.content},
        config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
    ):
        await res.stream_token(chunk)

    await res.send()

    memory.chat_memory.add_user_message(message.content)
    memory.chat_memory.add_ai_message(res.content)


@cl.on_settings_update
async def on_settings_update(settings):
    print("on_settings_update", settings)
    cl.user_session.set("settings", settings)  # Store updated settings in session
    await setup_runnable(settings)
