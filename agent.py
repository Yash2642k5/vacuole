import os
import ssl
import certifi
from typing import Literal, Union,List,TypedDict
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
from browser_use.llm import ChatOpenAI
from telegram import Update
from browser_use import ChatOllama,ChatGoogle, Agent, Controller
from pydantic import BaseModel
import asyncio
from browser_use import Agent, BrowserSession
from telegram import Update

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECOND_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
os.environ.pop("SSL_CERT_FILE", None)
os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context(cafile=certifi.where())

# Ovarall Schema of Graph state
class OverallState(TypedDict):
    history: Union[HumanMessage, AIMessage]
    user_input: str
    graph_output: str
    askAi_output: str
    browser_input: Union[str, List[str]]
    browser_output: str
    update: Update

# Browser response Schema
class BrowserData(BaseModel):
    url: str
    specifications: str
    price: str
    product_name: str

# List of browser response
class AllData(BaseModel):
    browser_data: List[BrowserData]

controller = Controller(output_model=AllData) 

# If no executable_path provided, uses Playwright/Patchright's built-in Chromium
browser_session = BrowserSession(
    # Path to a specific Chromium-based executable (optional)
    executable_path=None,  # macOS
    # Use a specific data directory on disk (optional, set to None for incognito)
    user_data_dir=None,   # this is the default
    # ... any other BrowserProfile or playwright launch_persistnet_context config...
    headless=True,
)

llm = ChatGoogle(
    model="gemini-2.5-pro",
    api_key=SECOND_GEMINI_API_KEY,
)


llm2 = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY,
)

# Graph Node 
async def browse(state: OverallState)->OverallState:
    agent = Agent(
        task=state['browser_input'],
        llm=llm,
        browser_session=browser_session,
        controller=controller
    )
    result = await agent.run()
    # print("................................Browser output.......................................")
    # print(result)
    # print(".......................................End................................")
    data = result.final_result()
    parsed: AllData = AllData.model_validate_json(data)    
    
    summary = "\n".join(
        f"- {item.product_name} costs {item.price}, has specifications '{item.specifications}' at {item.url}."
        for item in parsed.browser_data
    )

    state['browser_output'] = summary
    await state['update'].message.reply_text("85% task completed")
    return state