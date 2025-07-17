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
SECOND_GEMINI_API_KEY = os.getenv("SECOND_GEMINI_API_KEY")
os.environ.pop("SSL_CERT_FILE", None)
os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context(cafile=certifi.where())

class OverallState(TypedDict):
    user_input: Union[HumanMessage, AIMessage]
    graph_output: str
    askAi_output: str
    browser_input: Union[str, List[str]]
    browser_output: str
    update: Update


class BrowserData(BaseModel):
    url: str
    specifications: str
    price: str
    product_name: str

class AllData(BaseModel):
    browser_data: List[BrowserData]

controller = Controller(output_model=AllData) 

# If no executable_path provided, uses Playwright/Patchright's built-in Chromium
browser_session = BrowserSession(
    # Path to a specific Chromium-based executable (optional)
    executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',  # macOS

    # Use a specific data directory on disk (optional, set to None for incognito)
    user_data_dir='~/.config/browseruse/profiles/default',   # this is the default
    # ... any other BrowserProfile or playwright launch_persistnet_context config...
    headless=False,
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

async def browse(state: OverallState)->OverallState:
    # initial_action = [
    #     {'open-tab' : {'url': 'https://www.flipkart.com'}}
    # ]
    agent = Agent(
        task=state['browser_input'],
        llm=llm,
        browser_session=browser_session,
        controller=controller
    )
    result = await agent.run()
    data = result.final_result()
    parsed: AllData = AllData.model_validate_json(data)
    # print(data)
    
    
    summary = "\n".join(
        f"- {item.product_name} costs {item.price}, has specifications '{item.specifications}' at {item.url}."
        for item in parsed.browser_data
    )

    state['browser_output'] = summary
    print("summary type is", type(summary))
    print("summary is", summary)
    print("summary ends here")
    print("state output is",state["browser_output"])
    print("state output ends here")
    print(".............................................in browser function.............................")
    print(state)
    print("........................................ends .........................")
    await state['update'].message.reply_text("85% task completed")
    return state