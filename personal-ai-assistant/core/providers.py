"""
Provider-agnostic LLM interface.

Switch between OpenAI, Anthropic, or OpenRouter (which gives access to almost
any open or closed model) just by changing LLM_PROVIDER / LLM_MODEL /
LLM_API_KEY in your .env file. No code changes needed.
"""
from abc import ABC, abstractmethod
from typing import List, Dict
import requests


class LLMProvider(ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], system: str = "", max_tokens: int = 1500) -> str:
        """messages: [{"role": "user"|"assistant", "content": "..."}]"""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def chat(self, messages, system="", max_tokens=1500):
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system, messages=messages,
        )
        return "".join(block.text for block in resp.content if block.type == "text")


class OpenAIProvider(LLMProvider):
    def chat(self, messages, system="", max_tokens=1500):
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages
        resp = client.chat.completions.create(model=self.model, max_tokens=max_tokens, messages=full_messages)
        return resp.choices[0].message.content


class OpenRouterProvider(LLMProvider):
    """OpenRouter exposes an OpenAI-compatible REST API, so we call it directly
    with plain HTTP — this gives access to dozens of providers/models through
    one API key."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(api_key, model)
        self.base_url = base_url

    def chat(self, messages, system="", max_tokens=1500):
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": full_messages, "max_tokens": max_tokens},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def get_provider(provider_name: str, model: str, api_key: str, openrouter_base_url: str = None) -> LLMProvider:
    provider_name = provider_name.lower().strip()
    if provider_name == "anthropic":
        return AnthropicProvider(api_key, model)
    if provider_name == "openai":
        return OpenAIProvider(api_key, model)
    if provider_name == "openrouter":
        return OpenRouterProvider(api_key, model, openrouter_base_url or "https://openrouter.ai/api/v1")
    raise ValueError(f"Unknown provider '{provider_name}'. Use anthropic, openai, or openrouter.")
