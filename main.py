from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ai_agent import askAi

TOKEN: Final = 'yourTelegramToken'
BOT_USERNAME: Final = 'your botUsername'

#commands
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


#responses
async def handle_response (text: str) -> str:
    """handle responses

    Args:
        text (str): _description_

    Returns:
        str: _description_
    """
    response = await askAi(text)
    #print('Our Response: ', response)
    return response


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """handling messages

    Args:
        update (Update): _description_
        context (ContextTypes.DEFAULT_TYPE): _description_
    """
    message_type: str = update.message.chat.type
    text: str = update.message.text
    
    print(f'user ({update.message.chat.id}) in {message_type}: "{text}"')
    
    if message_type == 'group':
        if BOT_USERNAME in text:
            new_text: str = text.replace(BOT_USERNAME, '').strip()
            response: str = await handle_response(new_text)
        else:
            return
    else:
        response: str = await handle_response(text)
    
    #print('Bot: ', response)
    
    await update.message.reply_text(response)



async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error: {context.error}')
    



if __name__ == '__main__':
    print('starting bot....')
    app = Application.builder().token(TOKEN).build()
    
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