from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.project import Project
from app.models.conversation_message import ConversationMessage
from app.routers.auth import get_current_user, get_current_user_optional
from app.services.ai.factory import get_user_ai_config
from app.services.context import (
    build_project_context,
    save_ideation_messages,
    get_ideation_history,
    maybe_summarize,
)
from app.services.writing import stream_chat

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

IDEATION_SYSTEM_PROMPT = """You are an expert academic advisor and research supervisor. Help the user refine their research ideas into a well-defined academic paper. The user has a "Research Notes" panel on the right where they track their research plan.

The research notes fields are tailored to the paper type. When you discuss relevant topics, clearly state the field label followed by 中文冒号 and the value, so the system can auto-fill the notes panel. For example: 论文方向：... 核心概念 / 关键词：... 研究假设：... etc.

Your role:
1. Ask probing questions to understand the user's interests
2. Suggest research angles, methodologies, and designs appropriate for the paper type
3. Propose theoretical frameworks
4. Help the user design their study: variables, measurement tools, sample, procedure (if empirical); search strategy, inclusion criteria (if review); coding approach, data collection (if qualitative); propositions, concepts (if theoretical)
5. When you discuss these topics, state the field label followed by 中文冒号 and the value so the system can auto-fill

Guidelines:
- Be conversational and encouraging, like a real supervisor
- Guide the user through research design step by step
- Ask one question at a time
- Reference real academic concepts and theories
- Keep responses 2-3 paragraphs
- After sufficient discussion, ask if the user is ready to proceed to writing"""


@router.get("/projects/ideation/new")
async def new_ideation(request: Request):
    """Create a draft project and redirect to ideation page."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = Project(
            user_id=user.id,
            title="新项目（灵感中）",
            status="ideation",
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return RedirectResponse(f"/projects/{project.id}/ideation")


@router.get("/projects/{project_id}/ideation")
async def ideation_page(project_id: str, request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(
            Project,
            project_id,
            options=[selectinload(Project.outlines)],
        )
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        history = await get_ideation_history(project_id)

    from app.routers.project import TEMPLATES_LIST, JOURNAL_TEMPLATES, NOTE_FIELDS

    # Determine the template category
    template_category = "general"
    if project.template_name:
        for t in TEMPLATES_LIST:
            if t["name"] == project.template_name:
                template_category = t.get("category", "general")
                break

    note_fields = NOTE_FIELDS.get(template_category, NOTE_FIELDS["general"])

    return templates.TemplateResponse(
        "projects/ideation.html",
        {
            "request": request,
            "current_user": user,
            "project": project,
            "history": history,
            "content_templates": TEMPLATES_LIST,
            "journal_templates": JOURNAL_TEMPLATES,
            "note_fields": note_fields,
            "template_category": template_category,
        },
    )


@router.get("/api/projects/{project_id}/chat")
async def api_ideation_chat(
    project_id: str,
    message: str = Query(...),
    provider: str | None = Query(None),
    user=Depends(get_current_user),
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    user_config = await get_user_ai_config(user.id)
    history_data = await get_ideation_history(project_id)
    context = await build_project_context(project_id)

    # Save user message immediately
    await save_ideation_messages(project_id, [{"role": "user", "content": message}])

    # Build messages from history + summary + current user message
    messages = []
    if history_data["summary"]:
        messages.append({"role": "user", "content": "[对话历史摘要]\n" + history_data["summary"]})
    for m in history_data["messages"][-20:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    # Add context hint
    if context:
        messages.insert(0, {
            "role": "user",
            "content": "__system_context__\n" + context + "\n__end_context__"
        })

    full_response = ""

    async def event_stream():
        nonlocal full_response
        try:
            async for text in stream_chat(
                system_prompt=IDEATION_SYSTEM_PROMPT,
                messages=messages,
                provider=provider,
                user_config=user_config,
            ):
                full_response += text
                yield f"data: {json.dumps({'text': text})}\n\n"
            # Save AI response after stream completes
            if full_response:
                await save_ideation_messages(project_id, [{"role": "assistant", "content": full_response}])
                await maybe_summarize(project_id)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/projects/{project_id}/chat/save")
async def api_save_chat_messages(
    project_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Save chat messages (user message + AI response) to the database."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        messages = data.get("messages", [])

    await save_ideation_messages(project_id, messages)
    return {"ok": True}


@router.get("/api/projects/{project_id}/research-notes")
async def get_research_notes(project_id: str, user=Depends(get_current_user)):
    """Load saved research notes from project context."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)
        ctx = project.context or {}
        return {
            "topic": ctx.get("topic", ""),
            "keywords": ctx.get("keywords", ""),
            "methodology": ctx.get("methodology", ""),
            "experiment": ctx.get("experiment", ""),
            "theory": ctx.get("theory", ""),
            "contributions": ctx.get("contributions", ""),
            "draft": ctx.get("draft", ""),
        }


@router.post("/api/projects/{project_id}/research-notes")
async def save_research_notes(project_id: str, request: Request, user=Depends(get_current_user)):
    """Auto-save research notes to project context."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)
        data = await request.json()
        ctx = project.context or {}
        for field in ("topic", "keywords", "methodology", "experiment", "theory", "contributions", "draft"):
            if field in data:
                ctx[field] = data[field]
        project.context = ctx
        await db.commit()
    return {"ok": True}


@router.delete("/api/projects/{project_id}/chat/history")
async def clear_chat_history(project_id: str, user=Depends(get_current_user)):
    """Delete all conversation messages for this project."""
    from sqlalchemy import delete
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)
        await db.execute(
            delete(ConversationMessage).where(ConversationMessage.project_id == project_id)
        )
        await db.commit()
    return {"ok": True}


@router.post("/api/projects/{project_id}/ideation/confirm")
async def api_confirm_ideation(
    project_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    """Extract project info from conversation and finalize the project."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        title = data.get("title", project.title)
        context = data.get("context", {})

        project.title = title
        project.context = context
        project.status = "draft"
        await db.commit()

    return {"ok": True, "title": title}
