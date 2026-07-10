from __future__ import annotations
from app.services.ai import get_ai_provider
from app.services.ai.factory import AIProviderConfig


async def generate_outline(
    topic: str,
    description: str = "",
    context: str = "",
    provider: str | None = None,
    user_config: AIProviderConfig | None = None,
) -> dict:
    ai = get_ai_provider(name=provider, user_config=user_config)
    full_desc = description
    if context:
        full_desc = context + "\n\n" + description
    return await ai.generate_outline(topic, full_desc)


async def stream_chapter(
    topic: str,
    outline_json: dict,
    chapter_title: str,
    chapter_context: str = "",
    context: str = "",
    provider: str | None = None,
    previous_chapters: list[str] | None = None,
    user_config: AIProviderConfig | None = None,
):
    ai = get_ai_provider(name=provider, user_config=user_config)
    full_context = chapter_context
    if context:
        full_context = context + "\n\n章节背景: " + chapter_context
    async for text in ai.generate_chapter_stream(
        topic=topic,
        outline_json=outline_json,
        chapter_title=chapter_title,
        chapter_context=full_context,
        previous_chapters=previous_chapters,
    ):
        yield text


async def stream_rewrite(
    original_content: str,
    instruction: str,
    context: str = "",
    provider: str | None = None,
    user_config: AIProviderConfig | None = None,
):
    ai = get_ai_provider(name=provider, user_config=user_config)
    full_instruction = instruction
    if context:
        full_instruction = f"项目背景:\n{context}\n\n改写要求: {instruction}"
    async for text in ai.rewrite_stream(original_content, full_instruction):
        yield text


async def stream_chat(
    system_prompt: str,
    messages: list[dict[str, str]],
    provider: str | None = None,
    user_config: AIProviderConfig | None = None,
):
    ai = get_ai_provider(name=provider, user_config=user_config)
    async for text in ai.chat_stream(system_prompt, messages):
        yield text
