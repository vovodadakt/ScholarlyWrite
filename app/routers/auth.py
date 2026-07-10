from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.limits import limiter
from app.models.user import User

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
templates = Jinja2Templates(directory="app/templates")


async def get_current_user_optional(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        async with async_session() as db:
            user = await db.get(User, user_id_str)
            return user
    except (JWTError, ValueError):
        return None


async def get_current_user(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401)
    return user


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _set_auth_cookie(response: RedirectResponse, token: str):
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        secure=not settings.debug,
    )


@router.get("/auth/login")
async def login_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse("/projects")
    return templates.TemplateResponse(
        "auth/login.html", {"request": request, "current_user": None}
    )


@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "current_user": None, "error": "Invalid email or password"},
        )

    token = create_access_token(str(user.id))
    response = RedirectResponse("/projects", status_code=302)
    _set_auth_cookie(response, token)
    return response


@router.get("/auth/register")
async def register_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse("/projects")
    return templates.TemplateResponse(
        "auth/register.html", {"request": request, "current_user": None}
    )


@router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")
    display_name = form.get("display_name", "")

    if not email or not password or not display_name:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "current_user": None, "error": "All fields are required"},
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "current_user": None, "error": "Password must be at least 8 characters"},
        )

    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            return templates.TemplateResponse(
                "auth/register.html",
                {"request": request, "current_user": None, "error": "Email already registered"},
            )

        user = User(
            email=email,
            password_hash=pwd_context.hash(password),
            display_name=display_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    response = RedirectResponse("/projects", status_code=302)
    _set_auth_cookie(response, token)
    return response


@router.get("/auth/logout")
async def logout():
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response
