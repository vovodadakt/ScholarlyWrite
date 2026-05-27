from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.project import Project
from app.routers.auth import get_current_user, get_current_user_optional
from app.services.ai.factory import get_user_ai_config
from app.services.charts import (
    parse_csv, parse_pasted_text, generate_chart, recommend_chart,
    analyze_data_stream, recommend_chart_ai, list_sample_datasets, get_sample_dataset,
    compute_stats, preprocess_data,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/projects/{project_id}/data")
async def data_page(project_id: str, request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "projects/data.html",
        {"request": request, "current_user": user, "project": project},
    )


# ── Sample datasets ──

@router.get("/api/data/samples")
async def api_list_samples():
    """List available built-in sample datasets."""
    return {"samples": list_sample_datasets()}


@router.get("/api/data/samples/{key}")
async def api_get_sample(key: str):
    """Retrieve a sample dataset by key."""
    data = get_sample_dataset(key)
    if not data:
        raise HTTPException(status_code=404, detail=f"Sample dataset '{key}' not found")
    # Don't send all_rows to client to keep response small
    return {
        "columns": data["columns"],
        "rows": data["rows"],
        "types": data["types"],
        "total_rows": data["total_rows"],
        "all_rows": data["all_rows"],
    }


# ── Upload ──

@router.post("/api/projects/{project_id}/data/upload")
async def upload_data(
    project_id: str,
    file: UploadFile = File(...),
    encoding: str = Form("utf-8"),
    delimiter: str = Form(","),
    skip_rows: int = Form(0),
    header_row: int = Form(0),
    user=Depends(get_current_user),
):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    content = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext in ("csv", "txt"):
        result = parse_csv(content, encoding=encoding, delimiter=delimiter,
                           skip_rows=skip_rows, header_row=header_row)
    elif ext in ("xlsx", "xls"):
        try:
            import openpyxl
            import io as _io
            wb = openpyxl.load_workbook(_io.BytesIO(content), read_only=True)
            ws = wb.active
            rows = [[str(cell.value or "") for cell in row] for row in ws.iter_rows()]
            # Apply skip_rows and header_row for Excel too
            data_rows = rows[skip_rows:]
            if header_row < len(data_rows):
                cols = data_rows[header_row]
                body = data_rows[header_row + 1:]
            else:
                cols = data_rows[0] if data_rows else []
                body = data_rows[1:]
            cols = [c.strip().lstrip('﻿') or f"col_{i}" for i, c in enumerate(cols)]
            preview = body[:20]
            types = {}
            for ci, col in enumerate(cols):
                vals = [row[ci] for row in preview if ci < len(row) and row[ci].strip()]
                nc = sum(1 for v in vals if v.replace(".", "").replace("-", "").replace(",", "").isdigit())
                types[col] = "numeric" if vals and nc / len(vals) > 0.5 else "text"
            result = {"columns": cols, "rows": preview, "types": types, "total_rows": len(body),
                      "all_rows": body}
        except Exception:
            result = {"columns": [], "rows": [], "types": {}, "total_rows": 0, "all_rows": [],
                      "error": "无法解析 Excel 文件"}
    else:
        return {"error": "仅支持 CSV 和 Excel 文件"}

    return result


# ── Paste ──

@router.post("/api/projects/{project_id}/data/paste")
async def paste_data(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    body = await request.json()
    text = body.get("text", "")
    delimiter = body.get("delimiter", "auto")
    return parse_pasted_text(text, delimiter)


# ── URL import ──

@router.post("/api/projects/{project_id}/data/url-import")
async def url_import_data(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    body = await request.json()
    url = body.get("url", "")
    if not url:
        return {"error": "请输入 URL"}

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}: 无法获取文件"}
                content = await resp.read()
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}

    # Parse as CSV
    result = parse_csv(content, encoding=body.get("encoding", "utf-8"),
                       delimiter=body.get("delimiter", ","))
    return result


# ── Stats ──

@router.post("/api/projects/{project_id}/data/stats")
async def api_stats(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    data = await request.json()
    result = compute_stats(data)
    return {"stats": result}


# ── Preprocess ──

@router.post("/api/projects/{project_id}/data/preprocess")
async def api_preprocess(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    body = await request.json()
    data_info = body.get("data", {})
    operations = body.get("operations", [])
    if not operations:
        return {"error": "没有预处理操作"}

    result = preprocess_data(data_info, operations)
    return result


# ── Recommend ──

@router.post("/api/projects/{project_id}/data/recommend")
async def api_recommend_chart(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    data = await request.json()
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    x_col = data.get("x_col", columns[0] if columns else "")
    y_col = data.get("y_col", columns[1] if len(columns) > 1 else "")

    rec = recommend_chart({"columns": columns, "rows": rows}, x_col, y_col)
    return {"recommended": rec}


# ── AI Chart Recommend ──

@router.post("/api/projects/{project_id}/data/chart-recommend")
async def api_chart_recommend_ai(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    body = await request.json()
    data_info = {
        "columns": body.get("columns", []),
        "rows": body.get("rows", []),
        "types": body.get("types", {}),
        "total_rows": body.get("total_rows", 0),
    }
    user_config = await get_user_ai_config(user.id)
    rec = await recommend_chart_ai(data_info, user_config=user_config)
    if rec is None:
        raise HTTPException(status_code=500, detail="AI chart recommendation failed")
    return rec


# ── Chart ──

@router.post("/api/projects/{project_id}/data/chart")
async def create_chart(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    data = await request.json()
    columns = data.get("columns", [])
    rows = data.get("all_rows", data.get("rows", []))
    chart_type = data.get("chart_type", "bar")
    x_col = data.get("x_col", columns[0] if columns else "")
    y_col = data.get("y_col", columns[1] if len(columns) > 1 else "")

    theme = data.get("theme", "default")
    title = data.get("title", "")
    max_points = data.get("max_points", 0)
    fmt = data.get("format", "png")
    try:
        img = generate_chart(
            {"columns": columns, "rows": rows},
            chart_type, x_col, y_col, theme, title,
            max_points=max_points, fmt=fmt,
        )
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Chart error: {e}\n{traceback.format_exc()}")
    return {"image": img}


# ── Analyze ──

@router.post("/api/projects/{project_id}/data/analyze")
async def api_analyze_data(project_id: str, request: Request, user=Depends(get_current_user)):
    import json as _json

    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    body = await request.json()
    data_info = {
        "columns": body.get("columns", []),
        "rows": body.get("rows", []),
        "types": body.get("types", {}),
        "total_rows": body.get("total_rows", 0),
    }

    user_config = await get_user_ai_config(user.id)

    async def event_stream():
        full = ""
        try:
            async for text in analyze_data_stream(data_info, user_config=user_config):
                full += text
                yield f"data: {_json.dumps({'text': text})}\n\n"
            yield f"data: {_json.dumps({'done': True, 'full': full})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
