"""
Telegram gateway — talk to the same Agent from Telegram, anywhere.

1. Message @BotFather on Telegram, run /newbot, copy the token into
   TELEGRAM_BOT_TOKEN in your .env file.
2. Run:  python -m interfaces.telegram_bot
"""
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from config import settings, DB_PATH, SKILLS_DIR, JOBS_PATH
from core.memory import Memory
from core.skills import SkillLibrary
from core.agent import Agent
from core.scheduler import TaskScheduler

agent = Agent(settings, Memory(DB_PATH), SkillLibrary(SKILLS_DIR))
application = None  # set in __main__, used by notify()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm your personal AI assistant. Just message me normally.")


async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_chat.id)
    result = agent.learn_skill_from_recent(session_id)
    if result.get("worth_saving"):
        await update.message.reply_text(f"Saved a new skill: {result['name']}")
    else:
        await update.message.reply_text("Nothing distinct enough to save yet.")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_chat.id)
    reply = agent.handle_message(session_id, update.message.text)
    await update.message.reply_text(reply)


def notify(session_id: str, text: str):
    """Used by the scheduler to push proactive messages, e.g. a daily report."""
    async def _send():
        await application.bot.send_message(chat_id=int(session_id), text=text)
    asyncio.get_event_loop().create_task(_send())


if __name__ == "__main__":
    application = ApplicationBuilder().token(settings.telegram_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("learn", learn))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    scheduler = TaskScheduler(JOBS_PATH, agent, notify)
    scheduler.start()

    print("Telegram bot running...")
    application.run_polling()
