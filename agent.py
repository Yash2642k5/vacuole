import os
import ssl
import certifi
from typing import Literal, Union,List,TypedDict
from langchain_groq import ChatGroq
import os

class OverallState(TypedDict):
    user_input: str
    graph_output: str

os.environ.pop("SSL_CERT_FILE", None)
os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context(cafile=certifi.where())

from browser_use.llm import ChatOpenAI
from browser_use import ChatOllama,ChatGoogle, Agent, Controller
from pydantic import BaseModel
from typing import List

import asyncio

from browser_use import Agent, BrowserSession

class BrowserData(BaseModel):
    url: str
    search_queery: str
    price: str
    product_name: str

class AllData(BaseModel):
    browser_data: List[BrowserData]

controller = Controller(output_model=AllData) 

# If no executable_path provided, uses Playwright/Patchright's built-in Chromium
browser_session = BrowserSession(
    # Path to a specific Chromium-based executable (optional)
    executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',  # macOS
    # For Windows: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    # For Linux: '/usr/bin/google-chrome'

    # Use a specific data directory on disk (optional, set to None for incognito)
    user_data_dir='~/.config/browseruse/profiles/default',   # this is the default
    # ... any other BrowserProfile or playwright launch_persistnet_context config...
    # headless=False,
)

# llm = ChatOllama(
#     model="llama3.1:8b",
# )
llm = ChatGoogle(
    model="gemini-2.5-pro",
    api_key=GaminiAPiKey,
)


llm2 = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
    api_key=GroqApiKey,
)

async def browse(state: OverallState)->OverallState:
    # initial_action = [
    #     {'open-tab' : {'url': 'https://www.flipkart.com'}}
    # ]
    agent = Agent(
        task=state['user_input'],
        llm=llm,
        browser_session=browser_session,
    )
    result = await agent.run()
    data = result.final_result()
    # parsed: AllData = AllData.model_validate(data)
    print(data)
    data_filtered = llm2.invoke(f"Convert this into string ... {data}")
    state['graph-output'] = data_filtered
    return state


