"""Reference management: CRUD, search, DOI import, BibTeX, and formatting."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select

from app.database import async_session
from app.models.project import Project
from app.models.reference import Reference
from app.routers.auth import get_current_user
from app.services.references import (
    search_references, format_reference_list, format_reference,
    generate_bibtex, STYLE_META,
)
from app.services.doi import fetch_doi_metadata, parse_bibtex

router = APIRouter()


def _ref_to_dict(r: Reference) -> dict:
    return {
        "id": str(r.id),
        "project_id": r.project_id,
        "title": r.title,
        "authors": r.authors,
        "year": r.year,
        "journal": r.journal,
        "doi": r.doi,
        "url": r.url,
        "abstract": r.abstract,
        "citation_key": r.citation_key,
        "pub_type": r.pub_type,
        "volume": r.volume,
        "issue": r.issue,
        "pages": r.pages,
        "publisher": r.publisher,
        "raw_bibtex": r.raw_bibtex,
        "created_at": str(r.created_at) if r.created_at else "",
    }


@router.get("/api/references/search")
async def api_search_references(
    q: str = Query(...),
    limit: int = Query(10, ge=1, le=20),
    style: str = Query("apa"),
):
    results, error = await search_references(q, limit)
    if error:
        return {"results": [], "formatted": "", "error": error}

    formatted = format_reference_list(results, style) if results else ""
    return {"results": results, "formatted": formatted, "error": ""}


@router.get("/api/references/styles")
async def list_styles():
    """Return available citation styles."""
    return {"styles": [{"id": k, "name": v["name"], "type": v["type"]} for k, v in STYLE_META.items()]}


@router.post("/api/references/import/doi")
async def import_by_doi(request: Request):
    """Import reference metadata by DOI."""
    data = await request.json()
    doi = data.get("doi", "").strip()
    if not doi:
        raise HTTPException(status_code=400, detail="DOI is required")

    ref_data, error = await fetch_doi_metadata(doi)
    if error:
        raise HTTPException(status_code=404, detail=error)

    return {"ok": True, "data": ref_data}


@router.post("/api/references/import/bibtex")
async def import_bibtex(request: Request):
    """Parse BibTeX text and return reference data."""
    data = await request.json()
    text = data.get("bibtex", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="BibTeX text is required")

    refs, error = parse_bibtex(text)
    if error:
        raise HTTPException(status_code=400, detail=error)

    return {"ok": True, "data": refs, "count": len(refs)}


@router.get("/api/projects/{project_id}/references")
async def list_references(project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Reference)
            .where(Reference.project_id == project_id)
            .order_by(Reference.created_at.desc())
        )
        refs = result.scalars().all()
        return [_ref_to_dict(r) for r in refs]


@router.get("/api/projects/{project_id}/references/{ref_id}")
async def get_reference(project_id: str, ref_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        ref = await db.get(Reference, ref_id)
        if not ref or ref.project_id != project_id:
            raise HTTPException(status_code=404)

        return _ref_to_dict(ref)


@router.post("/api/projects/{project_id}/references")
async def add_reference(project_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()

        # auto-generate citation_key if not provided
        ck = data.get("citation_key", "").strip()
        if not ck:
            authors = data.get("authors", [])
            year = data.get("year", "")
            if authors:
                ck = authors[0].split()[-1].lower() if authors[0].split() else "ref"
            else:
                ck = "ref"
            if year:
                ck += str(year)
            # ensure uniqueness within project
            existing = await db.execute(
                select(Reference).where(
                    Reference.project_id == project_id,
                    Reference.citation_key.like(f"{ck}%"),
                )
            )
            existing_keys = {r.citation_key for r in existing.scalars().all()}
            base = ck
            n = 1
            while ck in existing_keys:
                ck = f"{base}{chr(96 + n)}"  # a, b, c...
                n += 1

        ref = Reference(
            project_id=project_id,
            title=data.get("title", ""),
            authors=data.get("authors", []),
            year=data.get("year"),
            journal=data.get("journal", ""),
            doi=data.get("doi", ""),
            url=data.get("url", ""),
            abstract=data.get("abstract", ""),
            citation_key=ck,
            pub_type=data.get("pub_type", "article"),
            volume=data.get("volume", ""),
            issue=data.get("issue", ""),
            pages=data.get("pages", ""),
            publisher=data.get("publisher", ""),
            raw_bibtex=data.get("raw_bibtex", ""),
        )
        db.add(ref)
        await db.commit()
        await db.refresh(ref)

    return {"ok": True, "id": str(ref.id), "citation_key": ref.citation_key}


@router.put("/api/projects/{project_id}/references/{ref_id}")
async def update_reference(project_id: str, ref_id: str, request: Request, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        ref = await db.get(Reference, ref_id)
        if not ref or ref.project_id != project_id:
            raise HTTPException(status_code=404)

        data = await request.json()
        for field in ["title", "authors", "year", "journal", "doi", "url", "abstract",
                       "citation_key", "pub_type", "volume", "issue", "pages",
                       "publisher", "raw_bibtex"]:
            if field in data:
                setattr(ref, field, data[field])

        await db.commit()

    return {"ok": True}


@router.delete("/api/projects/{project_id}/references/{ref_id}")
async def delete_reference(project_id: str, ref_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        ref = await db.get(Reference, ref_id)
        if not ref or ref.project_id != project_id:
            raise HTTPException(status_code=404)

        await db.delete(ref)
        await db.commit()

    return {"ok": True}


@router.post("/api/projects/{project_id}/references/batch-import")
async def batch_import_references(project_id: str, request: Request, user=Depends(get_current_user)):
    """Batch save multiple references at once."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        items = data.get("references", [])
        saved = []
        for item in items:
            ck = item.get("citation_key", "").strip()
            if not ck:
                authors = item.get("authors", [])
                year = item.get("year", "")
                if authors:
                    ck = authors[0].split()[-1].lower() if authors[0].split() else "ref"
                else:
                    ck = "ref"
                if year:
                    ck += str(year)

            ref = Reference(
                project_id=project_id,
                title=item.get("title", ""),
                authors=item.get("authors", []),
                year=item.get("year"),
                journal=item.get("journal", ""),
                doi=item.get("doi", ""),
                url=item.get("url", ""),
                abstract=item.get("abstract", ""),
                citation_key=ck,
                pub_type=item.get("pub_type", "article"),
                volume=item.get("volume", ""),
                issue=item.get("issue", ""),
                pages=item.get("pages", ""),
                publisher=item.get("publisher", ""),
                raw_bibtex=item.get("raw_bibtex", ""),
            )
            db.add(ref)
            saved.append(ref)

        await db.commit()
        for r in saved:
            await db.refresh(r)

    return {"ok": True, "count": len(saved), "keys": [r.citation_key for r in saved]}


@router.get("/api/projects/{project_id}/references/formatted")
async def format_references(
    project_id: str,
    style: str = Query("apa"),
    user=Depends(get_current_user),
):
    """Get formatted reference list for a project."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Reference).where(Reference.project_id == project_id)
        )
        refs = result.scalars().all()
        ref_list = [_ref_to_dict(r) for r in refs]

    formatted = format_reference_list(ref_list, style)
    return {"formatted": formatted, "count": len(ref_list)}


@router.get("/api/projects/{project_id}/references/export/bibtex")
async def export_bibtex(project_id: str, user=Depends(get_current_user)):
    """Export all project references as BibTeX."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(Reference).where(Reference.project_id == project_id)
        )
        refs = result.scalars().all()

    entries = [generate_bibtex(_ref_to_dict(r)) for r in refs]
    return {"bibtex": "\n\n".join(entries), "count": len(entries)}
