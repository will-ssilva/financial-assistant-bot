import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from .logic import start, respond, resumo, total_categoria, limpar, relatorio
import os

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

application = Application.builder().token(TELEGRAM_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("resumo", resumo))
application.add_handler(CommandHandler("total", total_categoria))
application.add_handler(CommandHandler("limpar", limpar))
application.add_handler(CommandHandler("relatorio", relatorio))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond))

async def telegram_webhook(request_data: str):
    update = Update.de_json(json.loads(request_data), application.bot)
    if not application._initialized:
        await application.initialize()
    await application.process_update(update)
