from operator import itemgetter
from typing import Dict, Optional
from operator import itemgetter
from typing import Dict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI # Keep for type hinting if needed, but not for instantiation
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder # Keep if used elsewhere, but not in setup_runnable
from langchain.schema.output_parser import StrOutputParser # Keep if used elsewhere
from langchain.schema.runnable import Runnable, RunnablePassthrough, RunnableLambda # Keep if used elsewhere
# from langchain.schema.runnables.config import RunnableConfig
from langchain_core.runnables import RunnableConfig
from langchain.memory import ConversationBufferMemory
from chainlit.types import ThreadDict
from chainlit.input_widget import Select, Switch, Slider
from app.ai.chatbot import create_chatbot_graph, State # Import the graph creation function and State
from app.ai.models.gemini import create_gemini_flash_model # Import the model creation function
from langchain_core.messages import HumanMessage, AIMessage # Import necessary message types
from langchain_core.language_models import BaseChatModel # Import for type hinting

import chainlit as cl


async def setup_runnable(settings: Dict):
    """
    Sets up the LangGraph runnable with the selected LLM model.
    """
    # Retrieve model settings
    gemini_model_name = settings.get("Gemini_Model", "gemini-2.0-flash")
    gemini_temperature = settings.get("Gemini_Temperature", 1.0) # Ensure float type

    # Create the LLM instance using the function from models.gemini
    llm = create_gemini_flash_model(model_name=gemini_model_name, temperature=gemini_temperature)

    # Create and compile the chatbot graph with the selected LLM
    compiled_graph = create_chatbot_graph(llm=llm)

    # Store the compiled graph in the user session
    cl.user_session.set("runnable", compiled_graph)


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
                max=1.0,
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

    # Memory is handled in on_chat_start and on_chat_resume, no need to set here
    # cl.user_session.set("memory", ConversationBufferMemory(return_messages=True))
    await setup_runnable(settings) # Call setup_runnable with the initial settings


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

    # Ensure settings are available, initialize with defaults if not
    if settings is None:
        settings = {
            "Gemini_Model": "gemini-2.0-flash",
            "Gemini_Temperature": 1.0, # Ensure float type
            "SAI_Steps": 30,
            "SAI_Cfg_Scale": 7,
            "SAI_Width": 512,
            "SAI_Height": 512,
        }
        cl.user_session.set("settings", settings) # Store defaults if initializing

    print("\nSettings:", settings, "\n")

    await setup_runnable(settings) # Call setup_runnable with the retrieved/default settings


@cl.on_message
async def on_message(message: cl.Message):
    memory = cl.user_session.get("memory")

    runnable = cl.user_session.get("runnable")

    if not message.content.strip():
        await message.reply("Please provide a valid question.")
        return

    res = cl.Message(content="")

    # Invoke the LangGraph graph
    initial_state = State(messages=[HumanMessage(content=message.content)])

    # Invoke the LangGraph graph to get the final state
    final_state = await runnable.ainvoke(
        initial_state,
        config=RunnableConfig(
            callbacks=[cl.LangchainCallbackHandler()],
            configurable={"thread_id": message.thread_id}
        ),
    )

    # Extract the final AI message from the state
    final_ai_message = None
    if "messages" in final_state:
        # Iterate in reverse to find the most recent AIMessage
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage):
                final_ai_message = msg
                break

    # Send the content of the final AI message
    if final_ai_message and final_ai_message.content:
        res.content = final_ai_message.content
        await res.send()
    else:
        # Handle case where no final AI message was found
        res.content = "Sorry, I could not generate a response."
        await res.send()

    memory.chat_memory.add_user_message(message.content)
    memory.chat_memory.add_ai_message(res.content)


@cl.on_settings_update
async def on_settings_update(settings):
    print("on_settings_update", settings)
    cl.user_session.set("settings", settings)  # Store updated settings in session
    await setup_runnable(settings) # Re-setup the runnable with new settings


@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(
            name="Okane Agents",
            markdown_description="Discuss finance news and sentiment analysis.",
            icon="/public/logo_light.png",
        )
    ]