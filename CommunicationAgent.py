from typing import Annotated, Any
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.graph import StateGraph,END
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.messages import HumanMessage,AIMessage
from typing import TypedDict,List,Union


from langchain.chains import LLMChain
from agent import browse
import asyncio

API_KEY = GaminiAPIKEy

from typing import Literal, Union,List,TypedDict
from pydantic import BaseModel,Field

class OverallState(TypedDict):
    user_input:List[Union[HumanMessage,AIMessage]]
    graph_output:str


llm = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
    api_key=GroqAPiKEY,
)
# Instantiate Gemini model with config
llm2 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # latest identifier
    google_api_key= API_KEY,
    temperature=0.7,
    max_tokens=1024,
)
llm3 = ChatGroq(
    model = "gemma2-9b-it",
    temperature=0,
    api_key=GroqAPiKEY
)

# for making the prompt or deciding the node what we have to do next either browser or Bypass browser
def get_messages(state: OverallState) -> OverallState:
    prompt = f"""
        You are a helpful prompt engineer. Given a user query, determine the user's intent in a structured format.

        1. If the user wants to purchase something:
        - First, identify and output the website name.
        - Then, list all relevant product details (e.g., product name, specifications, quantity, price if mentioned).

        Avoid any extra commentary or explanation. Output only the necessary details to help an automated browser tool take action.
        and User input is 
        {state['user_input']}
    """
    messages = llm.invoke(prompt)
    state['user-input'] = messages.content
    return state


def get_response(state: OverallState) -> OverallState:
    prompt = f"""
        You are a precise and helpful assistant.

        Given the following browser-use output from the user:
        {state['graph_output']}

        Provide a concise and clear response that summarizes the user's intent and the actions taken by the browser tool.
        and also include if the browser use sends a  product - link and description,price or some relevent data include that 
        in the response.
    """
    response = llm.invoke(prompt)
    state['graph_output'] = response.content
    return state



#create prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a friendly, knowledgeable ecommerce assistant named Sahayak. 
            Your role is to help users discover, compare, and understand products available online, especially budget-friendly 
            options in India. You speak clearly and concisely, using everyday language. Provide helpful suggestions and answer 
            questions related to categories like fashion, electronics, home goods, and deals. Always guide users politely, and 
            if you don't know something or lack real-time access, recommend searching online. Never give financial or medical advice. 
            Use emojis sparingly to make responses more engaging. Stay factual and avoid personal opinions.
     """),
    ("human", "{input}")
])
chain = LLMChain(llm=llm2, prompt=prompt)
# Async function to interact with Gemini using LangChain
def askAi(state:OverallState) -> OverallState:
    response = chain.invoke(input=state['user_input'])

    state['user-input'] = response["text"]
    return state


# to decide what to do next based on user input
def decidingAgent(state: OverallState) -> str:
    # if the user input contains any thing releted to the browser then only we will make call to browse function
    comptlete_input = f"""
        You are a helpful prompt engineer. Given a user query, determine the user's intent in a structured format.
        what is user intent 
        1. if the user wants to search something or purchase something or anything which requires the browser to answer then return browser
        2. otherwise return the genral.
        user input is {state['user_input']}

        Answer only a single word either browser or general.
        not more than one word.
    """
    response = llm3.invoke(comptlete_input).content
    print("deciding node",response)
    if 'browser' in response.lower():
        return "browse_node"
    elif 'general' in response.lower():
        return "get_messages_node"
    
    return "undefined"


# to write the content based on input
def writeContent(state: OverallState) -> OverallState:
    content = f"""
        You are a helpful prompt engineer. Given a user query.
        User input is {state['user_input']}
        Write the best answer based on the Your knowledge.
    """
    response = llm.invoke(content).content
    state['graph_output'] = response
    return state


workflow = StateGraph(OverallState)
workflow.add_node('first_node', askAi)
workflow.add_node('get_messages_node', get_messages)
workflow.add_node('browse_node', browse)
workflow.add_node('second_node', get_response)
workflow.add_node('genral_query_answer',writeContent)

workflow.set_entry_point('first_node')
workflow.set_finish_point('second_node')
workflow.add_conditional_edges(
    "first_node",
    decidingAgent,
    {
        "browse_node": "get_messages_node",
        "get_messages_node": "genral_query_answer",
        "undefined":"genral_query_answer"
    }
)
workflow.add_edge('get_messages_node', 'browse_node')
workflow.add_edge('browse_node', 'second_node')
workflow.add_edge('genral_query_answer', 'second_node')

graph = workflow.compile()

async def Communication(total_message: List[Union[HumanMessage,AIMessage]]) -> List[Union[HumanMessage,AIMessage]]:
    initial_state: OverallState = {
        'user_input': total_message,
        'graph_output': ""
    }
    
    final_state = await graph.ainvoke(initial_state)  # ✅ async invoke
    print(final_state['graph_output'])
    return final_state['graph_output']


# if __name__ == "__main__":
#     import asyncio
#     task = "Find me a budget-friendly smartphone under 15000 from flipkart also available on zip/pin code 303108."
#     result = asyncio.run(Communication(task))
#     print(result)
# print(graph)