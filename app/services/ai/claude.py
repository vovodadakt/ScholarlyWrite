from __future__ import annotations
import json
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from app.services.ai.base import BaseAIProvider

OUTLINE_SYSTEM_PROMPT = """You are an expert academic writing advisor. Given a paper topic and optional research context, generate a detailed, well-structured outline following the appropriate academic format.

The user may provide context from prior ideation discussions (包括关键词、推荐方法、理论框架等). Use this context to inform the outline structure.

If the context mentions a specific template or format (e.g., "IMRaD", "case study", "empirical research", "systematic review"), follow that format's section structure.

Return ONLY valid JSON in this exact format:
{
  "title": "Paper Title",
  "sections": [
    {
      "title": "Section Title",
      "subsections": [
        {"title": "Subsection Title"}
      ]
    }
  ]
}

Guidelines:
- Include 5-8 main sections appropriate for the paper type
- Each main section should have 2-4 subsections with specific, descriptive titles
- Section titles should reflect actual content, not just generic labels
- Write all titles in the same language as the topic
- Adapt the structure to the research approach (quantitative/qualitative/mixed)"""

CHAPTER_SYSTEM_PROMPT = """You are an expert academic writer. Write a detailed, well-researched chapter for an academic paper.
Write in a formal academic style. Include placeholders for citations in [Author, Year] format.
Write comprehensively: target 500-1000 words. Use proper paragraph structure and include subsection headings where appropriate."""


class ClaudeProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "",
    ):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)
        self.model = model

    async def generate_outline(self, topic: str, description: str = "") -> dict[str, Any]:
        user_message = f"Topic: {topic}"
        if description:
            user_message += f"\nAdditional instructions: {description}"

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            system=OUTLINE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
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

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=16384,
            system=CHAPTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def chat_stream(
        self, system_prompt: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=16384,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def rewrite_stream(
        self, original_content: str, instruction: str
    ) -> AsyncIterator[str]:
        user_message = f"""Original text:
{original_content}

Instruction: {instruction}

Rewrite the text above according to the instruction. Preserve the academic style and key information."""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=16384,
            system="You are an expert academic editor. Rewrite text according to the user's instructions.",
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
