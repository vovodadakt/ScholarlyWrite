from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.database import async_session
from app.models.project import Project
from app.models.experiment import Experiment
from app.routers.auth import get_current_user, get_current_user_optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

EXP_FIELDS = (
    "title", "objective", "hypothesis", "status", "tags",
    "steps", "materials", "equipment", "conditions", "images",
    "results_observations", "conclusion",
)


def _exp_dict(e: Experiment) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "objective": e.objective,
        "hypothesis": e.hypothesis,
        "status": e.status,
        "tags": e.tags,
        "steps": e.steps,
        "materials": e.materials,
        "equipment": e.equipment,
        "conditions": e.conditions,
        "images": e.images,
        "results_observations": e.results_observations,
        "conclusion": e.conclusion,
        "version": e.version,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.get("/projects/{project_id}/experiments")
async def experiments_page(project_id: str, request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "projects/experiments.html",
        {"request": request, "current_user": user, "project": project},
    )


@router.get("/api/projects/{project_id}/experiments")
async def list_experiments(project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Experiment)
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.created_at.desc())
        )
        return [_exp_dict(e) for e in result.scalars().all()]


@router.get("/api/projects/{project_id}/experiments/summaries")
async def list_experiment_summaries(project_id: str, user=Depends(get_current_user)):
    """Return short summaries for the 'insert experiment' dropdown."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Experiment)
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.created_at.desc())
        )
        return [
            {
                "id": e.id,
                "title": e.title,
                "status": e.status,
                "conclusion": e.conclusion[:200] if e.conclusion else "",
            }
            for e in result.scalars().all()
        ]


@router.get("/api/projects/{project_id}/experiments/export")
async def export_experiments(project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Experiment)
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.created_at.desc())
        )
        experiments = result.scalars().all()

        lines = [f"# 实验手册 — {project.title}\n"]
        for i, e in enumerate(experiments, 1):
            status_label = {"planned": "计划中", "in_progress": "进行中",
                            "completed": "已完成", "cancelled": "已取消"}.get(e.status, e.status)
            lines.append(f"## {i}. {e.title}")
            lines.append(f"- 状态: {status_label}  |  版本: v{e.version}  |  标签: {', '.join(e.tags or [])}")
            if e.objective:
                lines.append(f"- 目的: {e.objective}")
            if e.hypothesis:
                lines.append(f"- 假设: {e.hypothesis}")
            if e.materials:
                lines.append(f"- 材料/试剂: {', '.join(m.get('name', '') for m in e.materials)}")
            if e.equipment:
                lines.append(f"- 仪器设备: {', '.join(eq.get('name', '') for eq in e.equipment)}")
            if e.conditions:
                cond_parts = [f"{k}: {v}" for k, v in e.conditions.items() if v]
                if cond_parts:
                    lines.append(f"- 实验条件: {'; '.join(cond_parts)}")
            if e.steps:
                lines.append("- 实验步骤:")
                for s in e.steps:
                    desc = s.get("description", "")
                    exp_res = s.get("expected_result", "")
                    extra = f" (预期: {exp_res})" if exp_res else ""
                    lines.append(f"  {s.get('step_number', '?')}. {desc}{extra}")
            if e.results_observations:
                lines.append(f"- 结果与观察: {e.results_observations}")
            if e.conclusion:
                lines.append(f"- 结论: {e.conclusion}")
            lines.append("")

        return {"markdown": "\n".join(lines)}


@router.get("/api/projects/{project_id}/experiments/{exp_id}")
async def get_experiment(project_id: str, exp_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        experiment = await db.get(Experiment, exp_id)
        if not experiment or experiment.project_id != project_id:
            raise HTTPException(status_code=404)

        return _exp_dict(experiment)


@router.post("/api/projects/{project_id}/experiments")
async def create_experiment(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        exp = Experiment(project_id=project_id)
        for field in EXP_FIELDS:
            if field in data:
                setattr(exp, field, data[field])
        db.add(exp)
        await db.commit()
        await db.refresh(exp)
        return {"ok": True, "id": str(exp.id)}


@router.put("/api/projects/{project_id}/experiments/{exp_id}")
async def update_experiment(project_id: str, exp_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        experiment = await db.get(Experiment, exp_id)
        if not experiment or experiment.project_id != project_id:
            raise HTTPException(status_code=404)

        data = await request.json()
        for field in EXP_FIELDS:
            if field in data:
                setattr(experiment, field, data[field])

        experiment.version += 1
        await db.commit()
        return {"ok": True, "version": experiment.version}


@router.delete("/api/projects/{project_id}/experiments/{exp_id}")
async def delete_experiment(project_id: str, exp_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        experiment = await db.get(Experiment, exp_id)
        if not experiment or experiment.project_id != project_id:
            raise HTTPException(status_code=404)

        await db.delete(experiment)
        await db.commit()
        return {"ok": True}
