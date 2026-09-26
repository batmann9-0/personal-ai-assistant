"""
The Agent ties together: a provider (whichever LLM you've configured), memory
(who you are + conversation history), and skills (playbooks learned from past
tasks). Every interface — CLI, Telegram, Discord, web — calls this same Agent,
so behaviour and memory are consistent no matter where you talk to it from.
"""
from typing import Dict
from .providers import get_provider
from .memory import Memory
from .skills import SkillLibrary

BASE_SYSTEM_PROMPT = """You are a personal AI assistant that remembers the user \
across sessions and keeps a running model of who they are. Use the profile and \
relevant memories below to personalize your answers, but never fabricate facts \
you were not told. If a saved skill/playbook below matches the current request, \
follow its steps.

USER PROFILE:
{profile}

RELEVANT PAST CONTEXT:
{memories}

MATCHING SKILL (if any):
{skill}
"""


class Agent:
    def __init__(self, settings, memory: Memory, skills: SkillLibrary):
        self.settings = settings
        self.provider = get_provider(
            settings.provider, settings.model, settings.api_key, settings.openrouter_base_url
        )
        self.memory = memory
        self.skills = skills

    def _build_system_prompt(self, user_text: str) -> str:
        profile = self.memory.profile_as_text()
        memories = "\n".join(f"- {m}" for m in self.memory.search(user_text)) or "None found."
        skill = self.skills.find_matching(user_text)
        skill_text = f"{skill['name']}: {skill['playbook']}" if skill else "None."
        return BASE_SYSTEM_PROMPT.format(profile=profile, memories=memories, skill=skill_text)

    def handle_message(self, session_id: str, user_text: str) -> str:
        self.memory.add_message(session_id, "user", user_text)
        history = self.memory.recent_history(session_id, self.settings.max_history_messages)
        system_prompt = self._build_system_prompt(user_text)
        reply = self.provider.chat(history, system=system_prompt)
        self.memory.add_message(session_id, "assistant", reply)
        return reply

    def learn_skill_from_recent(self, session_id: str, turns: int = 6) -> Dict:
        """Call after a complex task so the assistant can distill it into a
        reusable skill for next time (CLI: /learn, Telegram/Discord: /learn)."""
        history = self.memory.recent_history(session_id, turns)
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        return self.skills.create_skill_from_transcript(self.provider, transcript)

    def remember_fact(self, key: str, value: str):
        self.memory.set_fact(key, value)
