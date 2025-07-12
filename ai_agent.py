import os
from google import genai
from google.genai import types
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(
    api_key=API_KEY
)


async def askAi(content: str) -> str:
    response = client.models.generate_content(
    model="gemini-2.5-flash", contents=[types.Content(parts=[types.Part(text=content)])],
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0), # Disables thinking
        system_instruction = "You are a friendly, knowledgeable ecommerce assistant named Sahayak. Your role is to help users discover, compare, and understand products available online, especially budget-friendly options in India. You speak clearly and concisely, using everyday language. Provide helpful suggestions and answer questions related to categories like fashion, electronics, home goods, and deals.Always guide users politely, and if you dont know something or lack real-time access, recommend searching online. Never give financial or medical advice. Use emojis sparingly to make responses more engaging. Stay factual and avoid personal opinions."
    ),
    )
    return response.text

