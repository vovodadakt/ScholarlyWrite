from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.chapter import Chapter
from app.models.chapter_snapshot import ChapterSnapshot
from app.models.outline import Outline
from app.models.project import Project
from app.routers.auth import get_current_user
from app.schemas.outline import OutlineGenerate, OutlineSave
from app.schemas.chapter import ChapterRewrite
from app.services.ai.factory import get_user_ai_config, get_ai_provider
from app.services.context import build_project_context, get_previous_chapter_summaries
from app.services.writing import generate_outline, stream_chapter, stream_rewrite

router = APIRouter()


@router.post("/api/projects/{project_id}/outline/generate")
async def api_generate_outline(
    project_id: str, data: OutlineGenerate, user=Depends(get_current_user)
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    user_config = await get_user_ai_config(user.id)
    context = await build_project_context(project_id)
    try:
        outline_data = await generate_outline(
            topic=data.topic or project.title,
            description=data.description or project.description,
            context=context,
            provider=data.provider,
            user_config=user_config,
        )
        return outline_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/projects/{project_id}/outline")
async def api_save_outline(
    project_id: str, data: OutlineSave, user=Depends(get_current_user)
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        # Upsert outline
        result = await db.execute(
            select(Outline).where(Outline.project_id == project_id)
        )
        outline = result.scalar_one_or_none()

        if outline:
            outline.content = data.content
        else:
            outline = Outline(project_id=project_id, content=data.content)
            db.add(outline)

        project.status = "outline_ready"
        await db.commit()

    return {"ok": True}


@router.get("/api/projects/{project_id}/chapters/stream")
async def api_stream_chapter(
    project_id: str,
    chapter_title: str = Query(...),
    chapter_context: str = Query(""),
    provider: str | None = Query(None),
    user=Depends(get_current_user),
):
    async with async_session() as db:
        project = await db.get(
            Project,
            project_id,
            options=[selectinload(Project.outlines), selectinload(Project.chapters)],
        )
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        outline = project.outlines[0] if project.outlines else None
        if not outline:
            raise HTTPException(status_code=400, detail="No outline found. Generate an outline first.")

        outline_json = outline.content
        previous = [
            f"{c.title}: {c.content[:300]}" for c in sorted(project.chapters, key=lambda c: c.chapter_order)
        ]

    user_config = await get_user_ai_config(user.id)
    context = await build_project_context(project_id)

    async def event_stream():
        try:
            async for text in stream_chapter(
                topic=project.title,
                outline_json=outline_json,
                chapter_title=chapter_title,
                chapter_context=chapter_context,
                context=context,
                provider=provider,
                previous_chapters=previous if previous else None,
                user_config=user_config,
            ):
                yield f"data: {json.dumps({'text': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/projects/{project_id}/chapters/{chapter_id}/rewrite")
async def api_rewrite_chapter(
    project_id: str,
    chapter_id: str,
    data: ChapterRewrite,
    user=Depends(get_current_user),
):
    async with async_session() as db:
        chapter = await db.get(Chapter, chapter_id)
        if not chapter or str(chapter.project_id) != project_id:
            raise HTTPException(status_code=404)

        # Verify project ownership
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        original_content = chapter.content

    user_config = await get_user_ai_config(user.id)
    context = await build_project_context(project_id)

    async def event_stream():
        try:
            async for text in stream_rewrite(
                original_content=original_content,
                instruction=data.instruction,
                context=context,
                provider=data.provider,
                user_config=user_config,
            ):
                yield f"data: {json.dumps({'text': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/projects/{project_id}/chapters")
async def api_create_chapter(request: Request, project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        title = data.get("title", "").strip()
        content = data.get("content", "")
        chapter_order = data.get("chapter_order", 0)
        parent_id = data.get("parent_id")
        chapter_number = data.get("chapter_number", "")
        level = data.get("level", 1)

        if not title:
            raise HTTPException(status_code=400, detail="Chapter title is required")

        # Check if chapter with same title exists in this project
        result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.title == title,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            existing.status = "ai_generated"
            existing.parent_id = parent_id
            existing.chapter_number = chapter_number
            existing.level = level
            chapter_id = str(existing.id)
        else:
            chapter = Chapter(
                project_id=project_id,
                title=title,
                content=content,
                chapter_order=chapter_order,
                status="ai_generated",
                parent_id=parent_id,
                chapter_number=chapter_number,
                level=level,
            )
            db.add(chapter)
            await db.flush()
            chapter_id = str(chapter.id)

        # Auto-create snapshot
        result3 = await db.execute(
            select(ChapterSnapshot).where(ChapterSnapshot.chapter_id == chapter_id)
            .order_by(ChapterSnapshot.version.desc()).limit(1)
        )
        last_snap = result3.scalar_one_or_none()
        next_version = (last_snap.version + 1) if last_snap else 1
        snap = ChapterSnapshot(
            chapter_id=chapter_id,
            content=content,
            version=next_version,
        )
        db.add(snap)

        project.status = "writing"
        await db.commit()

    return {"ok": True, "id": chapter_id}


@router.get("/api/projects/{project_id}/chapters/{chapter_id}")
async def api_get_chapter(
    project_id: str, chapter_id: str, user=Depends(get_current_user)
):
    async with async_session() as db:
        chapter = await db.get(Chapter, chapter_id)
        if not chapter or str(chapter.project_id) != project_id:
            raise HTTPException(status_code=404)

        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        return {
            "id": str(chapter.id),
            "title": chapter.title,
            "content": chapter.content,
            "chapter_order": chapter.chapter_order,
            "chapter_number": chapter.chapter_number or "",
            "level": chapter.level,
            "parent_id": chapter.parent_id,
            "status": chapter.status,
        }


@router.post("/api/projects/{project_id}/auto-fill")
async def api_auto_fill(project_id: str, request: Request, user=Depends(get_current_user)):
    """Auto-fill all chapters based on outline + context.
    Generate all content first, then save in a single DB transaction."""
    async with async_session() as db:
        project = await db.get(
            Project, project_id,
            options=[selectinload(Project.outlines), selectinload(Project.chapters)],
        )
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        outline = project.outlines[0] if project.outlines else None
        if not outline:
            raise HTTPException(status_code=400, detail="No outline found")

        user_config = await get_user_ai_config(user.id)
        context = await build_project_context(project_id)
        outline_json = outline.content

    async def event_stream():
        generated: list[dict] = []
        try:
            import json as _json
            sections = outline_json.get("sections", [])
            ai = get_ai_provider(name=None, user_config=user_config)

            for si, section in enumerate(sections):
                yield f"data: {_json.dumps({'status': 'generating', 'section': section['title']})}\n\n"
                chapter_text = ""
                async for text in ai.generate_chapter_stream(
                    topic=project.title,
                    outline_json=outline_json,
                    chapter_title=section["title"],
                    chapter_context=context,
                    previous_chapters=[],
                ):
                    chapter_text += text
                    yield f"data: {_json.dumps({'text': text})}\n\n"

                generated.append({
                    "title": section["title"],
                    "content": chapter_text,
                    "chapter_order": si,
                })

                # Generate subsections
                for sub in section.get("subsections", []):
                    sub_title = section["title"] + " — " + sub["title"]
                    yield f"data: {_json.dumps({'status': 'generating', 'section': sub_title})}\n\n"
                    sub_text = ""
                    async for text in ai.generate_chapter_stream(
                        topic=project.title,
                        outline_json=outline_json,
                        chapter_title=sub_title,
                        chapter_context=context + f"\n\n上一节内容:\n{chapter_text[:500]}",
                        previous_chapters=[chapter_text[:500]],
                    ):
                        sub_text += text
                        yield f"data: {_json.dumps({'text': text})}\n\n"

                    generated.append({
                        "title": sub_title,
                        "content": sub_text,
                        "chapter_order": si,
                    })

            # Save all generated chapters in one transaction
            yield f"data: {_json.dumps({'status': 'saving', 'section': ''})}\n\n"
            async with async_session() as db_save:
                project_save = await db_save.get(Project, project_id)
                for g in generated:
                    result = await db_save.execute(
                        select(Chapter).where(
                            Chapter.project_id == project_id,
                            Chapter.title == g["title"],
                        )
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.content = g["content"]
                        existing.status = "ai_generated"
                    else:
                        ch = Chapter(
                            project_id=project_id,
                            title=g["title"],
                            content=g["content"],
                            chapter_order=g["chapter_order"],
                            status="ai_generated",
                        )
                        db_save.add(ch)
                if project_save:
                    project_save.status = "writing"
                await db_save.commit()

            yield f"data: {_json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/projects/{project_id}/chapters/{chapter_id}/snapshots")
async def api_list_snapshots(chapter_id: str, project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(ChapterSnapshot)
            .where(ChapterSnapshot.chapter_id == chapter_id)
            .order_by(ChapterSnapshot.version.desc())
            .limit(20)
        )
        snaps = result.scalars().all()
        return [
            {
                "id": str(s.id),
                "version": s.version,
                "content_preview": s.content[:200],
                "created_at": s.created_at.isoformat() if s.created_at else "",
            }
            for s in snaps
        ]


@router.post("/api/projects/{project_id}/chapters/{chapter_id}/restore")
async def api_restore_snapshot(
    project_id: str,
    chapter_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        snapshot_id = data.get("snapshot_id", "")

        snap = await db.get(ChapterSnapshot, snapshot_id)
        if not snap or snap.chapter_id != chapter_id:
            raise HTTPException(status_code=404)

        chapter = await db.get(Chapter, chapter_id)
        chapter.content = snap.content
        await db.commit()

        return {"ok": True, "content": snap.content}
