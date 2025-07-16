import os
from typing import Final
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv
from database import getDataBase
from datetime import datetime, timezone
from firebase_admin import firestore

db = firestore.client()
import nest_asyncio
nest_asyncio.apply()

load_dotenv()
TELEGRAM_BOT_TOKEN: Final = os.getenv("TOKEN")
TELEGRAM_BOT_USERNAME: Final = os.getenv("BOT_USERNAME")
API_KEY = os.getenv("GEMINI_API_KEY")

db = getDataBase()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a greeting message when the /start command is issued.

    Args:
        update (Update): Incoming update from Telegram.
        context (ContextTypes.DEFAULT_TYPE): Context object with metadata and bot data.
    """
    await update.message.reply_text(
        "Hello, give me a description of the product you want to search and let's get going!!!!"
    )


async def help_command (update: Update, context: ContextTypes.DEFAULT_TYPE):
    """sends a message to user when confused

    Args:
        update (Update): _description_
        context (ContextTypes.DEFAULT_TYPE): _description_
    """
    await update.message.reply_text("Give me a description of the product you want to buy to get started.")




def append_chat_message(user_id: str, role: str, content: str):
    user_ref = db.collection('users').document(str(user_id))

    new_message = {
        'role': role,
        'content': content,
        'timestamp': datetime.now(timezone.utc)
    }

    try:
        data_to_set = {
            'chats': firestore.ArrayUnion([new_message])
        }
        user_ref.set(data_to_set, merge=True)
        print(f"Message for user '{user_id}' added successfully. Role: {role}, Content: '{content}'")
    except Exception as e:
        print(f"Error appending message for user '{user_id}': {e}")



def get_chat_history(user_id: str):
    user_ref = db.collection('users').document(str(user_id))

    try:
        user_doc = user_ref.get()
        if user_doc.exists:
            chat_history = user_doc.to_dict().get('chats', [])

            if not chat_history:
                return []  # No messages yet

            # Sort by timestamp (latest first)
            sorted_chats = sorted(
                chat_history,
                key=lambda msg: msg.get('timestamp', datetime.min),
                reverse=True
            )

            # Return the latest 10 or fewer messages
            return sorted_chats[:10]
        else:
            print(f"User with ID '{user_id}' not found.")
            return []
    except Exception as e:
        print(f"Error fetching chat history for user '{user_id}': {e}")
        return []



def convert_to_chat_messages(chat_history: list):
    converted_messages = []

    for msg in chat_history:
        role = msg.get('role')
        content = msg.get('content', '')

        if role == 'user':
            converted_messages.append(HumanMessage(content=content))
        elif role == 'assistant':
            converted_messages.append(AIMessage(content=content))
        else:
            print(f"Skipping unknown role: {role}")

    return converted_messages


from CommunicationAgent import Communication
from langchain_core.messages import HumanMessage,AIMessage
from collections import defaultdict
conversation_history = defaultdict(list)
import asyncio
def handle_response (update: Update, text: str, user_id:str) -> str:
    """handle responses

    Args:
        text (str): _description_

    Returns:
        str: _description_
    """
    # response = askAi(text)
    conversation_history[user_id].append(HumanMessage(content=text))
    response = asyncio.run(Communication(update, conversation_history[user_id]))
    conversation_history[user_id].append(AIMessage(content=response))
    # response = "Hello my name is vacuole and i am here for your help .........."
    # print('Our Response: ', response)
    return response


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """handling messages

    Args:
        update (Update): _description_
        context (ContextTypes.DEFAULT_TYPE): _description_
    """
    message_type: str = update.message.chat.type
    text: str = update.message.text
    user_id: str = update.effective_user.id 
    # username: str = update.effective_user.username
    
    print(f'user ({update.message.chat.id}) in {message_type}: "{text}"')
    print("in the handle_message function =>",user_id)
    
    if message_type == 'group':
        if TELEGRAM_BOT_USERNAME in text:
            new_text: str = text.replace(TELEGRAM_BOT_USERNAME, '').strip()
            # conversation_history.append(new_text)
            response: str = handle_response(update, new_text,user_id)
            # conversation_history.append(response)
        else:
            return
    else:
        response: str = handle_response(update,text,user_id)
    
    #print('Bot: ', response)
    
    await update.message.reply_text(response)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error: {context.error}')
    


from telegram.ext import Application, CommandHandler, MessageHandler, filters
print('starting bot....')
app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

#commands
app.add_handler(CommandHandler('start', start_command))
app.add_handler(CommandHandler('help', help_command))

#messsages
app.add_handler(MessageHandler(filters.TEXT, handle_message))

#errors
app.add_error_handler(error)

#polls the bot
print("polling...")
app.run_polling(poll_interval=3)