from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.figure import Figure
from app.models.project import Project
from app.models.reference import Reference
from app.routers.auth import get_current_user
from app.services.export import build_docx, build_latex, build_pdf, build_cover_letter

router = APIRouter()


def _safe_header_filename(filename: str) -> dict:
    """Return Content-Disposition header dict with RFC 5987 filename encoding."""
    encoded = quote(filename, safe="")
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}


async def _get_export_data(project_id: str, user):
    async with async_session() as db:
        project = await db.get(
            Project, project_id, options=[selectinload(Project.chapters)]
        )
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        chapters = sorted(project.chapters, key=lambda c: c.chapter_order)
        chapter_list = [
            {"title": ch.title, "content": ch.content} for ch in chapters
        ]

        result = await db.execute(
            select(Reference).where(Reference.project_id == project_id)
        )
        refs = result.scalars().all()
        reference_list = [
            {
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "journal": r.journal,
                "doi": r.doi,
                "citation_key": r.citation_key,
                "pub_type": r.pub_type,
                "volume": r.volume,
                "issue": r.issue,
                "pages": r.pages,
                "publisher": r.publisher,
                "url": r.url,
                "abstract": r.abstract,
            }
            for r in refs
        ]

        journal_style = project.journal_style or "apa"

        result2 = await db.execute(
            select(Figure)
            .where(Figure.project_id == project_id)
            .order_by(Figure.figure_number)
        )
        figs = result2.scalars().all()
        figure_list = [
            {
                "id": f.id,
                "filename": f.filename,
                "caption": f.caption,
                "alt_text": f.alt_text,
                "figure_number": f.figure_number,
                "width": f.width,
                "storage_path": f.storage_path,
            }
            for f in figs
        ]

    return project.title, chapter_list, reference_list, figure_list, journal_style


@router.get("/api/projects/{project_id}/export/docx")
async def export_docx(project_id: str, user=Depends(get_current_user)):
    title, chapter_list, reference_list, figure_list, journal_style = await _get_export_data(project_id, user)
    buf = build_docx(title=title, chapters=chapter_list, references=reference_list, figures=figure_list, journal_style=journal_style)
    headers = _safe_header_filename(f"{title[:50]}.docx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.get("/api/projects/{project_id}/export/latex")
async def export_latex(project_id: str, user=Depends(get_current_user)):
    title, chapter_list, reference_list, figure_list, journal_style = await _get_export_data(project_id, user)
    tex = build_latex(title=title, chapters=chapter_list, references=reference_list, figures=figure_list, journal_style=journal_style)
    headers = _safe_header_filename(f"{title[:50]}.tex")
    return Response(
        content=tex,
        media_type="application/x-tex",
        headers=headers,
    )


@router.get("/api/projects/{project_id}/export/pdf")
async def export_pdf(project_id: str, user=Depends(get_current_user)):
    title, chapter_list, reference_list, figure_list, journal_style = await _get_export_data(project_id, user)
    buf = build_pdf(title=title, chapters=chapter_list, references=reference_list, figures=figure_list, journal_style=journal_style)
    headers = _safe_header_filename(f"{title[:50]}.pdf")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers=headers,
    )


@router.post("/api/projects/{project_id}/cover-letter")
async def generate_cover_letter(project_id: str, request: Request, user=Depends(get_current_user)):
    from app.database import async_session as _as

    data = await request.json()
    journal_name = data.get("journal_name", "")
    editor_name = data.get("editor_name", "")
    highlights = data.get("highlights", [])
    custom_message = data.get("custom_message", "")

    async with _as() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        title = project.title
        authors = user.display_name or ""
        js = project.journal_style or ""

    buf = build_cover_letter(
        project_title=title,
        authors=authors,
        journal_name=journal_name or js or "the journal",
        editor_name=editor_name,
        highlights=highlights,
        custom_message=custom_message,
    )
    headers = _safe_header_filename(f"cover_letter_{title[:30]}.docx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
