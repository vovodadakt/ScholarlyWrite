import traceback

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.database import engine
from app.limits import limiter
from app.models.base import Base
from app.migrate import auto_migrate
from app.routers import auth as auth_router
from app.routers import project as project_router
from app.routers import writing as writing_router
from app.routers import export as export_router
from app.routers import settings as settings_router
from app.routers import ideation as ideation_router
from app.routers import references as references_router
from app.routers import data as data_router
from app.routers import experiments as experiments_router
from app.routers import search as search_router
from app.routers import latex as latex_router
from app.routers import figures as figures_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await auto_migrate(engine)
    yield


app = FastAPI(title="ScholarlyWrite", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(project_router.router)
app.include_router(writing_router.router)
app.include_router(export_router.router)
app.include_router(settings_router.router)
app.include_router(ideation_router.router)
app.include_router(references_router.router)
app.include_router(data_router.router)
app.include_router(experiments_router.router)
app.include_router(search_router.router)
app.include_router(latex_router.router)
app.include_router(figures_router.router)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        host = request.headers.get("host", "")

        if origin and host not in origin:
            return JSONResponse({"detail": "CSRF check failed"}, status_code=403)
        if referer and host not in referer:
            return JSONResponse({"detail": "CSRF check failed"}, status_code=403)

    response = await call_next(request)
    return response


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        {"detail": f"Page not found: {request.url.path}"},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    if settings.debug:
        return JSONResponse(
            {"detail": str(exc), "traceback": traceback.format_exc()},
            status_code=500,
        )
    return JSONResponse(
        {"detail": "服务器内部错误，请稍后重试"},
        status_code=500,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log to file for debugging
    try:
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(f"\n=== {traceback.format_exc()} ===\n")
    except Exception:
        pass
    if isinstance(exc, HTTPException):
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )
    if settings.debug:
        return JSONResponse(
            {
                "detail": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc().split("\n"),
            },
            status_code=500,
        )
    return JSONResponse(
        {"detail": "服务器内部错误，请稍后重试"},
        status_code=500,
    )


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return RedirectResponse("/auth/login")
