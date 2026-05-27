from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_outline(self, topic: str, description: str = "") -> dict[str, Any]:
        """Generate a structured paper outline from a topic."""

    @abstractmethod
    async def generate_chapter_stream(
        self,
        topic: str,
        outline_json: dict[str, Any],
        chapter_title: str,
        chapter_context: str,
        previous_chapters: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Stream-generate chapter content."""

    @abstractmethod
    async def rewrite_stream(
        self, original_content: str, instruction: str
    ) -> AsyncIterator[str]:
        """Stream-rewrite content based on instruction."""

    @abstractmethod
    async def chat_stream(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Stream a general chat conversation."""
