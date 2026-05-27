from __future__ import annotations
import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.services.ai.base import BaseAIProvider
from app.services.ai.claude import (
    CHAPTER_SYSTEM_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
)


class OpenAIProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "",
    ):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)
        self.model = model

    async def generate_outline(self, topic: str, description: str = "") -> dict[str, Any]:
        user_message = f"Topic: {topic}"
        if description:
            user_message += f"\nAdditional instructions: {description}"

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": OUTLINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            max_tokens=16384,
        )

        text = response.choices[0].message.content
        return json.loads(text)

    async def generate_chapter_stream(
        self,
        topic: str,
        outline_json: dict[str, Any],
        chapter_title: str,
        chapter_context: str,
        previous_chapters: list[str] | None = None,
    ) -> AsyncIterator[str]:
        outline_str = json.dumps(outline_json, indent=2, ensure_ascii=False)
        prev_context = ""
        if previous_chapters:
            prev_context = "\n\nPrevious chapters summary:\n" + "\n".join(
                previous_chapters
            )

        user_message = f"""Paper topic: {topic}

Full outline:
{outline_str}

Now write the chapter: "{chapter_title}"
Context: {chapter_context}
{prev_context}

Write this chapter in full academic style. Include a brief introduction to the chapter, the main content with subsections, and a transition to the next chapter."""

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": CHAPTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=16384,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def chat_stream(
        self, system_prompt: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(messages)
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            max_tokens=16384,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def rewrite_stream(
        self, original_content: str, instruction: str
    ) -> AsyncIterator[str]:
        user_message = f"""Original text:
{original_content}

Instruction: {instruction}

Rewrite the text above according to the instruction. Preserve the academic style and key information."""

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert academic editor. Rewrite text according to the user's instructions.",
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=16384,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
