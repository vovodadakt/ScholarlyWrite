from __future__ import annotations
from dataclasses import dataclass, field

from app.config import settings
from app.services.ai.base import BaseAIProvider
from app.services.ai.claude import ClaudeProvider
from app.services.ai.openai import OpenAIProvider

# Providers that use Anthropic Messages API
CLAUDE_FORMAT_PROVIDERS = {"claude"}

# Providers that use OpenAI-compatible Chat Completions API
OPENAI_FORMAT_PROVIDERS = {"openai", "deepseek", "openrouter", "zhipu", "moonshot", "qwen", "groq", "ollama"}

PRESET_PROVIDERS = [
    {
        "id": "claude",
        "name": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com",
        "models": [
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-1-20250805",
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-5.5",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5.1",
            "o4-mini",
            "o3",
            "o3-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": [
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "deepseek-v3.2",
            "deepseek-v3.1-terminus",
            "deepseek-chat",
            "deepseek-reasoner",
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-opus-4-7",
            "openai/gpt-5.4",
            "openai/o4-mini",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-reasoner",
            "google/gemini-3-flash",
            "qwen/qwen3-235b-a22b",
        ],
    },
    {
        "id": "zhipu",
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            "glm-5.1",
            "glm-5",
            "glm-4.7",
            "glm-4.6",
            "glm-4.5",
            "glm-z1-airx",
            "glm-z1-air",
            "glm-z1-flash",
        ],
    },
    {
        "id": "moonshot",
        "name": "Moonshot Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": [
            "kimi-k2.6",
            "kimi-k2.5",
            "moonshot-v1-auto",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ],
    },
    {
        "id": "qwen",
        "name": "通义千问 (阿里)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen3.6-max-preview",
            "qwen3.6-plus",
            "qwen3.6-flash",
            "qwen3-max",
            "qwen-plus",
            "qwen3-coder-plus",
            "qwen-turbo",
        ],
    },
    {
        "id": "groq",
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "qwen-2.5-coder-32b",
            "qwen-qwq-32b",
            "llama-3.1-8b-instant",
        ],
    },
    {
        "id": "ollama",
        "name": "Ollama (本地)",
        "base_url": "http://localhost:11434/v1",
        "models": [
            "llama3",
            "mistral",
            "phi3",
            "gemma3",
            "qwen3",
        ],
    },
    {
        "id": "custom",
        "name": "自定义",
        "base_url": "",
        "models": [],
    },
]


@dataclass
class AIProviderConfig:
    provider: str = ""
    api_key: str = ""
    api_base_url: str = ""
    model: str = ""


def get_ai_provider(
    name: str | None = None,
    user_config: AIProviderConfig | None = None,
) -> BaseAIProvider:
    # Resolve provider
    provider_name = name or settings.default_ai_provider
    if user_config and user_config.provider:
        provider_name = user_config.provider

    # Resolve API key
    api_key = ""
    base_url = ""
    model = ""

    if provider_name == "claude":
        api_key = user_config.api_key if user_config and user_config.api_key else settings.anthropic_api_key
        if user_config and user_config.api_base_url:
            base_url = user_config.api_base_url
        model = user_config.model if user_config and user_config.model else settings.default_ai_model
        if not model.startswith("claude"):
            model = "claude-sonnet-4-20250514"
        if not api_key:
            raise ValueError("Claude API key not configured. Set it in Settings.")
        return ClaudeProvider(api_key=api_key, model=model, base_url=base_url)

    # OpenAI-compatible providers
    if provider_name in OPENAI_FORMAT_PROVIDERS:
        api_key = user_config.api_key if user_config and user_config.api_key else settings.openai_api_key
        if user_config and user_config.api_base_url:
            base_url = user_config.api_base_url
        if not api_key:
            raise ValueError(f"API key for '{provider_name}' not configured.")
        model = user_config.model if user_config and user_config.model else settings.default_ai_model
        if not model:
            # Look up preset default
            for preset in PRESET_PROVIDERS:
                if preset["id"] == provider_name:
                    model = preset["models"][0] if preset["models"] else ""
                    break
        if not base_url:
            for preset in PRESET_PROVIDERS:
                if preset["id"] == provider_name:
                    base_url = preset["base_url"]
                    break
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)

    raise ValueError(f"Unknown AI provider: {provider_name}")


async def get_user_ai_config(user_id: str) -> AIProviderConfig | None:
    from sqlalchemy import select
    from app.database import async_session
    from app.models.user_settings import UserSettings
    from app.services.crypto import decrypt_api_key

    async with async_session() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        us = result.scalar_one_or_none()
        if us and us.api_key:
            return AIProviderConfig(
                provider=us.ai_provider,
                api_key=decrypt_api_key(us.api_key),
                api_base_url=us.api_base_url,
                model=us.ai_model,
            )
    return None
