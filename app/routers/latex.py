import os
import shutil
import subprocess
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.figure import Figure
from app.models.project import Project
from app.models.reference import Reference
from app.routers.auth import get_current_user, get_current_user_optional
from app.services.export import build_latex

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/projects/{project_id}/latex")
async def latex_page(project_id: str, request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

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
            }
            for r in refs
        ]

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

    tex_source = build_latex(title=project.title, chapters=chapter_list, references=reference_list, figures=figure_list)

    return templates.TemplateResponse(
        "projects/latex.html",
        {
            "request": request,
            "current_user": user,
            "project": project,
            "tex_source": tex_source,
        },
    )


@router.get("/api/projects/{project_id}/latex/source")
async def get_latex_source(project_id: str, user=Depends(get_current_user)):
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
            }
            for r in refs
        ]

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

    tex = build_latex(title=project.title, chapters=chapter_list, references=reference_list, figures=figure_list)
    return {"source": tex}


def _compile_local(tex_source: str) -> bytes | None:
    """Try local LaTeX engines. Checks: tectonic (bundled), xelatex, pdflatex."""
    tex_source = tex_source.replace("\r\n", "\n")
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "paper.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_source)

        # 1. Try bundled tectonic.exe (drop it in project root, ~30MB)
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        tectonic = root / "tectonic.exe"
        if tectonic.exists():
            try:
                subprocess.run(
                    [str(tectonic), "--outdir", tmpdir, "paper.tex"],
                    cwd=tmpdir, capture_output=True, timeout=120,
                )
                pdf_path = os.path.join(tmpdir, "paper.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read()
            except Exception:
                pass

        # 2. Try system xelatex / pdflatex
        for engine in ("xelatex", "pdflatex"):
            try:
                subprocess.run(
                    [engine, "-interaction=nonstopmode", "-halt-on-error", "paper.tex"],
                    cwd=tmpdir, capture_output=True, timeout=30,
                )
                subprocess.run(
                    [engine, "-interaction=nonstopmode", "-halt-on-error", "paper.tex"],
                    cwd=tmpdir, capture_output=True, timeout=30,
                )
                pdf_path = os.path.join(tmpdir, "paper.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read()
            except Exception:
                continue
    return None


@router.post("/api/projects/{project_id}/latex/compile")
async def compile_latex(project_id: str, request: Request, user=Depends(get_current_user)):
    """Compile LaTeX to PDF. Tries local engine first, falls back to remote service."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    data = await request.json()
    tex_source = data.get("source", "")

    # Try local compilation first
    pdf_bytes = _compile_local(tex_source)
    if pdf_bytes is not None:
        return Response(content=pdf_bytes, media_type="application/pdf")

    # If local LaTeX engine not found, report specifically
    from pathlib import Path
    tectonic_path = Path(__file__).parent.parent.parent / "tectonic.exe"
    if not shutil.which("xelatex") and not shutil.which("pdflatex") and not tectonic_path.exists():
        raise HTTPException(
            status_code=400,
            detail="未检测到 LaTeX 编译器。轻量方案：下载 tectonic.exe (~30MB) 放到项目根目录 pythonProject/ 下即可。下载地址: https://github.com/tectonic-typesetting/tectonic/releases"
        )

    # Local compilation failed (LaTeX syntax error, etc.)
    raise HTTPException(
        status_code=500,
        detail="LaTeX 编译失败，请检查源码中的语法错误。提示：中文论文需使用 xelatex 编译。"
    )
