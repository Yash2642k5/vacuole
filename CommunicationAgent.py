import os
from dotenv import load_dotenv
from typing import Annotated, Any
from telegram import Update
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.graph import StateGraph,END
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.messages import HumanMessage,AIMessage
from typing import TypedDict,List,Union
from telegram import Update
from langchain.chains import LLMChain
from agent import browse
import asyncio

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECOND_GEMINI_API_KEY = os.getenv("SECOND_GEMINI_API_KEY")
API_KEY = os.getenv('GEMINI_API_KEY')

from typing import Literal, Union,List,TypedDict
from pydantic import BaseModel,Field

class OverallState(TypedDict):
    user_input: Union[HumanMessage, AIMessage]
    graph_output:str
    askAi_output: str
    browser_input: Union[str, List[str]]
    browser_output: str
    update: Update


llm = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY,
)
# Instantiate Gemini model with config
llm2 = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",  # latest identifier
    google_api_key= API_KEY,
    temperature=0.7,
    max_tokens=1024,
)
llm3 = ChatGroq(
    model = "gemma2-9b-it",
    temperature=0,
    api_key=GROQ_API_KEY
)

# for making the prompt or deciding the node what we have to do next either browser or Bypass browser
async def get_messages(state: OverallState) -> OverallState:
    input_prompt = f"""
        Identify the user's intent based on the given query in a structured format, and 
        Very important thing is that, dont forget to mention your output that- give answer in text only, dont make any files to give answer and if make a bullet point list in text if required. avoid irrelevent data and focus on only giving what was asked

        Provide the output concisely without any commentary or additional explanations. Only include details necessary to assist an automated browser tool in executing the purchase action.

        # Steps
        1. If purchase intent is confirmed, extract the website name if not mentioned then open "Flipkart.com" .
        2. Now identify the product name provided by user and search on the search-bar
        3. Extract product details: product name, specifications, quantity,product-link, and price (if any).
        4. Format the extracted information clearly and concisely.
        5. if the user ask you to check any product availability then check the availability of the product on the website and if available then give the product details and if not available search for similar result which are available.

        Omit any fields that are not mentioned in the query. If the user query does not indicate a purchase intent, respond with an empty JSON object:

        # Examples
        Input: "I want to buy the latest iPhone 14 on Apple.com, two units."
        Output:
        1. first search Flipkat.com
        2. open flipkart.com
        3. search for "iphone 14" in the search bar
        4. click on the first product 
        5. extact the product details 

        Input: "Find me a gaming laptop with 16GB RAM and 1TB SSD on Amazon."
        Output:
        1. first Search Amazon.in
        2. open Amazon.in
        3. search for "gaming laptop with 16GB RAM and 1TB SSD" in the search bar
        4. click on the first product 
        5. extract the product details

        and User input is 
        {state['askAi_output']}
    """
    messages = llm2.invoke(input_prompt)
    state['browser_input'] = messages.content
    await state['update'].message.reply_text("35% task completed")
    return state


async def get_response(state: OverallState) -> OverallState:
    input_prompt = f"""
    You are Vacuole, a friendly and knowledge-able ecommerce assistant specialized in helping users discover, compare, and understand products available online, especially budget-friendly options in India. 
    Communicate clearly and concisely using everyday language. Your expertise covers categories including fashion, electronics, home goods, and deals.
    When interacting with users, provide helpful product suggestions and answer their questions politely and informatively.
    
    Use emojis sparingly to make your responses more engaging without overwhelming the message. Always maintain a factual tone and avoid sharing personal opinions.
    
    # Response Guidelines
    - Be friendly, clear, and concise.
    - Cover fashion, electronics, home goods, and deals.
    - Use simple, everyday language.
    - Avoid providing financial or medical advice.
    - If uncertain or lacking information, politely recommend searching online.
    - Use minimal emojis to enhance engagement.
    - Stay factual and impartial.

    # Output Format
    Provide responses in natural, conversational text addressing the user's queries or requests following the above guidelines, with minimal and appropriate emoji use where suitable.


    Given the following automatic-browser output(answer based on the user query) from the user and don't mention that you are getting any input always talk like you are the one doing all the work in order to create an abstraction for the user:\n
        {state['browser_output']}

    Identify if the browser output includes details about a product, such as a product link, description, price, or any other relevant data.
    Include that product information in the summary if available.

    # Steps
    - Understand the user's browsing activity and what they were looking for.
    - Summarize the intent behind the browsing session.
    - Identify actions the browser tool performed (searches done, pages visited, etc.).
    - Detect any product-related information in the output (links, description, price).
    - Summarize all findings into a clear, concise response.

    # Output Format

    Provide the output as a concise list for every product and take no more than 100 words for a product and for each product on the list show:
    - product information, include the product's link, description, price, or relevant details.
    """
    response = llm2.invoke(input_prompt)
    state['graph_output'] = response.content
    print("..................................................")
    print("graph_output is: ", state["graph_output"])
    print("..................................................")
    print("in the get_response node of the graph the final updates are ....................")
    print(state)
    print("..................................................")
    await state['update'].message.reply_text("95% task completed")
    return state


async def askAi(state: OverallState) -> OverallState:
    prompt = f"""
        You are an intelligent assistant agent. Your task is to analyze the user's recent and past messages.
        Based on the full chat history provided in: {state['user_input']}, regenerate the user's last question in a condensed form.
        - Focus on **keywords** instead of full sentences.
        - **Grammar is not important** .
        - Limit the output to **100 words**.
        - The output must include enough **context** from chat history for a browser agent to understand and take appropriate action.
        Your goal is to provide a **compressed, keyword-rich query** that accurately reflects the user's intent.
    """
    response = llm2.invoke(prompt)
    state['askAi_output'] = response.content
    await state['update'].message.reply_text("20% task completed")
    return state


# to decide what to do next based on user input
async def decidingAgent(state: OverallState) -> str:
    # if the user input contains any thing releted to the browser then only we will make call to browse function
    # print("..................................................")
    # print("Latest state user_input", state['user_input'][-1])
    # print("..................................................")
    comptlete_input = f"""
        You are a helpful prompt engineer. Given a user query, determine the user's intent in a structured format.
        what is user intent 
        1. if the user wants to search something or purchase something or anything which requires the browser to answer then return browser
        2. otherwise return the genral.
        user input is {state['user_input'][0]}
        Answer only a single word either browser or general.
        not more than one word.
    """
    response = llm3.invoke(comptlete_input).content
    print("deciding node",response)
    if 'browser' in response.lower():
        await state['update'].message.reply_text("10% task completed")
        return "browse_node"
    elif 'general' in response.lower():
        await state['update'].message.reply_text("50% task completed")
        return "get_messages"
    return "undefined"


# to write the content based on input
async def writeContent(state: OverallState) -> OverallState:
    prompt = f"""
    You are Vacuole, a friendly and knowledgeable ecommerce assistant specialized in helping users discover, compare, and understand products available online, especially budget-friendly options in India. Communicate clearly and concisely using everyday language. Your expertise covers categories including fashion, electronics, home goods, and deals.
    When interacting with users, provide helpful product suggestions and answer their questions politely and informatively. If you don't know an answer or lack real-time information, courteously advise users to search online. Avoid giving any financial or medical advice. Use emojis sparingly to make your responses more engaging without overwhelming the message. Always maintain a factual tone and avoid sharing personal opinions.

    # Response Guidelines
    - Be friendly, clear, and concise.
    - Focus on budget-friendly options in India.
    - Cover fashion, electronics, home goods, and deals.
    - Use simple, everyday language.
    - Avoid providing financial or medical advice.
    - If uncertain or lacking information, politely recommend searching online.
    - Use minimal emojis to enhance engagement.
    - Stay factual and impartial.

    # Output Format
        Provide responses in natural, conversational text addressing the user's queries or requests following the above guidelines, with minimal and appropriate emoji use where suitable.
    # User Input is :
    {state['user_input']}
    """
    response = llm.invoke(prompt).content
    state['graph_output'] = response
    await state['update'].message.reply_text("90% task completed")
    return state

def stater(state: OverallState) -> OverallState:
    """This function is used to set the initial state of the graph"""
    return state

workflow = StateGraph(OverallState)
workflow.add_node('first_node', stater)
workflow.add_node('askAi_node', askAi)
workflow.add_node('get_messages_node', get_messages)
workflow.add_node('browse_node', browse)
workflow.add_node('second_node', get_response)
workflow.add_node('genral_query_answer',writeContent)

workflow.set_entry_point('first_node')
workflow.set_finish_point('second_node')
workflow.add_conditional_edges(
    'first_node',
    decidingAgent,
    {
        "browse_node": "askAi_node",
        "get_messages": "genral_query_answer",
        "undefined":"genral_query_answer"
    }
)
workflow.add_edge('askAi_node', 'get_messages_node')
workflow.add_edge('get_messages_node', 'browse_node')
workflow.add_edge('browse_node', 'second_node')
workflow.add_edge('genral_query_answer', END)

graph = workflow.compile()

async def Communication(update: Update, total_message: List[Union[HumanMessage,AIMessage]]) -> List[Union[HumanMessage,AIMessage]]:
    initial_state: OverallState = {
        'user_input': total_message,
        'graph_output': "",
        'browser_output': "",
        'askAi_output': "",
        'browser_input': [],
        'update': update
    }
    
    final_state = await graph.ainvoke(initial_state)  # ✅ async invoke
    # print("the final answer is :", final_state)
    return final_state['graph_output']
