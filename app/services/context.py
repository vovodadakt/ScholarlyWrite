import json
import re

from sqlalchemy import select, func

from app.database import async_session
from app.models.conversation_message import ConversationMessage
from app.models.chapter import Chapter


async def build_project_context(project_id: str) -> str:
    """Assemble full context for AI calls: key info + conversation + chapter summaries."""
    async with async_session() as db:
        # Project context dict
        from app.models.project import Project
        project = await db.get(Project, project_id)
        if not project:
            return ""

        parts = []

        # 1. Key info from research notes (dynamic fields)
        if project.context:
            ctx = project.context
            parts.append(f"## 论文信息\n题目: {ctx.get('topic', project.title)}")

            # Define label mapping for common fields
            field_labels = {
                "keywords": "关键词",
                "hypothesis": "研究假设",
                "variables": "变量定义",
                "methodology": "研究方法",
                "sample": "样本与数据",
                "instruments": "测量工具",
                "experiment": "实验设计",
                "research_questions": "研究问题",
                "search_strategy": "检索策略",
                "inclusion_criteria": "纳入标准",
                "quality_assessment": "质量评价",
                "analysis_method": "分析方法",
                "data_collection": "数据收集",
                "coding_approach": "编码策略",
                "quant_method": "量化方法",
                "qual_method": "质性方法",
                "integration": "整合策略",
                "theory_gap": "理论缺口",
                "concepts": "概念界定",
                "propositions": "理论命题",
                "scope": "边界条件",
                "theory": "理论框架",
                "contributions": "预期贡献",
                "notes": "备注",
            }
            for key, label in field_labels.items():
                val = ctx.get(key)
                if val:
                    if isinstance(val, list):
                        parts.append(f"{label}: {', '.join(val)}")
                    else:
                        parts.append(f"{label}: {val}")

            if ctx.get("draft"):
                parts.append(f"\n## 草稿笔记\n{ctx.get('draft')}")
            if ctx.get("content_template"):
                parts.append(f"\n内容模板: {ctx.get('content_template')}")

        # 2. Conversation summary
        if project.conversation_summary:
            parts.append("\n## 历史对话摘要\n" + project.conversation_summary)

        # 3. Ideation conversation (last 15 rounds)
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.project_id == project_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(30)
        )
        messages = list(result.scalars().all())
        if messages:
            messages.reverse()
            parts.append("\n## 最近对话记录")
            for m in messages:
                role_label = "用户" if m.role == "user" else "AI"
                parts.append(f"{role_label}: {m.content}")

        # 3. Chapter summaries
        result2 = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_order)
        )
        chapters = list(result2.scalars().all())
        if chapters:
            parts.append("\n## 已写章节摘要")
            for ch in chapters:
                summary = ch.content[:500].replace("\n", " ")
                parts.append(f"- {ch.title}: {summary}...")

        # 4. Experiments
        from app.models.experiment import Experiment
        result3 = await db.execute(
            select(Experiment)
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.created_at.desc())
        )
        experiments = list(result3.scalars().all())
        if experiments:
            parts.append("\n## 实验记录")
            for exp in experiments:
                parts.append(f"- [{exp.status}] {exp.title}")
                if exp.objective:
                    parts.append(f"  目的: {exp.objective[:200]}")
                if exp.conclusion:
                    parts.append(f"  结论: {exp.conclusion[:300]}")

        return "\n\n".join(parts)


async def get_previous_chapter_summaries(project_id: str) -> list[str]:
    """Get short summaries of all chapters for injection."""
    async with async_session() as db:
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_order)
        )
        chapters = result.scalars().all()
        return [
            f"{ch.title}: {ch.content[:300]}" for ch in chapters
        ]


async def save_ideation_messages(
    project_id: str, messages: list[dict]
) -> None:
    """Batch save conversation messages for a project."""
    async with async_session() as db:
        for m in messages:
            msg = ConversationMessage(
                project_id=project_id,
                role=m["role"],
                content=m["content"],
            )
            db.add(msg)
        await db.commit()


_notes_strip = re.compile(r'\n{0,2}\[研究笔记\]\n\{[^}]*\}\s*$', re.DOTALL)

MAX_HISTORY_MSGS = 30
SUMMARY_TRIGGER = 40


async def maybe_summarize(project_id: str) -> None:
    """If conversation exceeds SUMMARY_TRIGGER, summarize oldest messages into project.conversation_summary."""
    async with async_session() as db:
        from app.models.project import Project
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.project_id == project_id)
            .order_by(ConversationMessage.created_at)
        )
        all_msgs = result.scalars().all()
        if len(all_msgs) <= SUMMARY_TRIGGER:
            return

        proj = await db.get(Project, project_id)
        if not proj:
            return

        # Summarize messages older than the most recent MAX_HISTORY_MSGS
        old = all_msgs[: -MAX_HISTORY_MSGS]
        lines = []
        for m in old:
            role = "用户" if m.role == "user" else "AI"
            content = _notes_strip.sub('', (m.content or "")).rstrip()
            # Truncate each message to keep summary compact
            lines.append(f"{role}: {content[:300]}")
        raw = "\n".join(lines)

        # Try AI summarization if available, otherwise use truncated text
        summary = _build_local_summary(raw, proj.conversation_summary)
        proj.conversation_summary = summary
        await db.commit()


def _build_local_summary(raw: str, existing_summary: str) -> str:
    """Build a compact summary from raw conversation text without calling AI.
    Keeps the existing summary as prefix, appends new key points."""
    # Extract key sentences (those with substantive content)
    lines = raw.split("\n")
    key_lines = []
    for line in lines:
        line = line.strip()
        if len(line) > 40:  # substantive lines
            key_lines.append(line[:200])
    new_part = "\n".join(key_lines[-20:])  # Keep last 20 key lines
    if existing_summary:
        # Keep existing summary, add separator, add new key lines
        existing_short = existing_summary[-2000:] if len(existing_summary) > 2000 else existing_summary
        return existing_short + "\n---\n" + new_part
    return new_part


async def get_ideation_history(project_id: str) -> dict:
    """Get recent ideation messages + conversation summary for a project.

    Returns:
        {"messages": [...], "summary": str, "total_count": int}
    Only the last 30 messages are returned. Older messages are distilled into summary.
    """
    async with async_session() as db:
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.project_id == project_id)
            .order_by(ConversationMessage.created_at)
        )
        all_messages = result.scalars().all()
        total = len(all_messages)

        from app.models.project import Project
        proj = await db.get(Project, project_id)
        summary = proj.conversation_summary if proj else ""

        recent = all_messages[-30:] if total > 30 else all_messages
        return {
            "messages": [
                {"role": m.role, "content": _notes_strip.sub('', (m.content or "")).rstrip()}
                for m in recent
            ],
            "summary": summary,
            "total_count": total,
        }
