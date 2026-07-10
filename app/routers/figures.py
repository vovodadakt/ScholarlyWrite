import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.database import async_session
from app.models.figure import Figure
from app.models.project import Project
from app.routers.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "figures")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".tif"}


@router.get("/api/projects/{project_id}/figures")
async def list_figures(project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Figure)
            .where(Figure.project_id == project_id)
            .order_by(Figure.figure_number)
        )
        figures = result.scalars().all()
        return [
            {
                "id": f.id,
                "filename": f.filename,
                "caption": f.caption,
                "alt_text": f.alt_text,
                "figure_number": f.figure_number,
                "width": f.width,
                "storage_path": f.storage_path,
            }
            for f in figures
        ]


@router.post("/api/projects/{project_id}/figures/upload")
async def upload_figure(
    project_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    figure_number: int = Form(0),
    user=Depends(get_current_user),
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    ext = os.path.splitext(file.filename or "image.png")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}。支持: {', '.join(ALLOWED_EXTENSIONS)}")

    safe_name = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"figures/{safe_name}"
    abs_path = os.path.join(UPLOAD_DIR, safe_name)

    content = await file.read()
    with open(abs_path, "wb") as f:
        f.write(content)

    async with async_session() as db:
        # Auto-assign figure number if not provided
        if figure_number == 0:
            result = await db.execute(
                select(Figure.figure_number)
                .where(Figure.project_id == project_id)
                .order_by(Figure.figure_number.desc())
                .limit(1)
            )
            last = result.scalar_one_or_none()
            figure_number = (last + 1) if last else 1

        fig = Figure(
            project_id=project_id,
            filename=file.filename or "image.png",
            caption=caption,
            figure_number=figure_number,
            storage_path=rel_path,
        )
        db.add(fig)
        await db.commit()
        await db.refresh(fig)

        return {
            "id": fig.id,
            "filename": fig.filename,
            "caption": fig.caption,
            "figure_number": fig.figure_number,
            "width": fig.width,
            "storage_path": fig.storage_path,
        }


@router.put("/api/projects/{project_id}/figures/{figure_id}")
async def update_figure(
    project_id: str,
    figure_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        fig = await db.get(Figure, figure_id)
        if not fig or fig.project_id != project_id:
            raise HTTPException(status_code=404)

        data = await request.json()
        for field in ("caption", "alt_text", "figure_number", "width"):
            if field in data:
                setattr(fig, field, data[field])
        await db.commit()
        return {"ok": True}


@router.delete("/api/projects/{project_id}/figures/{figure_id}")
async def delete_figure(project_id: str, figure_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        fig = await db.get(Figure, figure_id)
        if not fig or fig.project_id != project_id:
            raise HTTPException(status_code=404)

        # Delete file from disk
        abs_path = os.path.join(
            os.path.dirname(__file__), "..", "static", fig.storage_path
        )
        try:
            os.remove(abs_path)
        except FileNotFoundError:
            pass

        await db.delete(fig)
        await db.commit()
        return {"ok": True}


@router.get("/api/projects/{project_id}/figures/{figure_id}/file")
async def get_figure_file(project_id: str, figure_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        fig = await db.get(Figure, figure_id)
        if not fig or fig.project_id != project_id:
            raise HTTPException(status_code=404)

    abs_path = os.path.join(os.path.dirname(__file__), "..", "static", fig.storage_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    return FileResponse(abs_path)
