"""
Discord gateway — talk to the same Agent from Discord, anywhere.

1. Create an application + bot at https://discord.com/developers/applications,
   enable "Message Content Intent", copy the token into DISCORD_BOT_TOKEN.
2. Invite the bot to your server, then run: python -m interfaces.discord_bot
"""
import asyncio
import discord

from config import settings, DB_PATH, SKILLS_DIR, JOBS_PATH
from core.memory import Memory
from core.skills import SkillLibrary
from core.agent import Agent
from core.scheduler import TaskScheduler

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
agent = Agent(settings, Memory(DB_PATH), SkillLibrary(SKILLS_DIR))


def notify(session_id: str, text: str):
    async def _send():
        channel = client.get_channel(int(session_id))
        if channel:
            await channel.send(text)
    asyncio.get_event_loop().create_task(_send())


@client.event
async def on_ready():
    print(f"Discord bot logged in as {client.user}")
    scheduler = TaskScheduler(JOBS_PATH, agent, notify)
    scheduler.start()


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if message.content.strip() == "/learn":
        result = agent.learn_skill_from_recent(str(message.channel.id))
        await message.channel.send(
            f"Saved a new skill: {result['name']}" if result.get("worth_saving")
            else "Nothing distinct enough to save yet."
        )
        return
    reply = agent.handle_message(str(message.channel.id), message.content)
    await message.channel.send(reply)


if __name__ == "__main__":
    client.run(settings.discord_token)
