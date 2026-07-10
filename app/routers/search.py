from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.conversation_message import ConversationMessage
from app.routers.auth import get_current_user_optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/search")
async def search_page(request: Request, q: str = Query("")):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    results = {"projects": [], "chapters": [], "conversations": []}

    if q.strip():
        async with async_session() as db:
            # Search projects
            r1 = await db.execute(
                select(Project)
                .where(Project.user_id == user.id)
                .where(
                    or_(
                        Project.title.ilike(f"%{q}%"),
                        Project.description.ilike(f"%{q}%"),
                    )
                )
                .limit(10)
            )
            results["projects"] = [
                {"id": str(p.id), "title": p.title, "description": p.description[:100]}
                for p in r1.scalars().all()
            ]

            # Search chapters across all user projects
            user_projects = await db.execute(
                select(Project.id).where(Project.user_id == user.id)
            )
            project_ids = [r[0] for r in user_projects.all()]
            if project_ids:
                r2 = await db.execute(
                    select(Chapter)
                    .where(Chapter.project_id.in_(project_ids))
                    .where(Chapter.content.ilike(f"%{q}%"))
                    .options(selectinload(Chapter.project))
                    .limit(10)
                )
                results["chapters"] = [
                    {
                        "id": str(c.id),
                        "title": c.title,
                        "project_title": c.project.title,
                        "project_id": str(c.project_id),
                        "preview": c.content[:200],
                    }
                    for c in r2.scalars().all()
                ]

                # Search conversations
                r3 = await db.execute(
                    select(ConversationMessage)
                    .where(ConversationMessage.project_id.in_(project_ids))
                    .where(ConversationMessage.content.ilike(f"%{q}%"))
                    .options(selectinload(ConversationMessage.project))
                    .limit(10)
                )
                results["conversations"] = [
                    {
                        "id": str(c.id),
                        "role": c.role,
                        "project_title": c.project.title,
                        "project_id": str(c.project_id),
                        "preview": c.content[:200],
                    }
                    for c in r3.scalars().all()
                ]

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "current_user": user,
            "query": q,
            "results": results,
        },
    )
