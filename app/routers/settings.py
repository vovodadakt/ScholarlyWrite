from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.database import async_session
from app.models.user_settings import UserSettings
from app.routers.auth import get_current_user, get_current_user_optional
from app.services.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings")
async def settings_page(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings_obj = result.scalar_one_or_none()

    # Decrypt API key for display (show masked)
    if settings_obj and settings_obj.api_key:
        try:
            decrypted = decrypt_api_key(settings_obj.api_key)
            masked = decrypted[:4] + "****" + decrypted[-4:] if len(decrypted) > 8 else "****"
        except Exception:
            masked = "****"
    else:
        masked = ""

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "current_user": user,
            "settings": settings_obj,
            "api_key_masked": masked,
        },
    )


@router.post("/api/settings")
async def save_settings(request: Request, user=Depends(get_current_user)):
    data = await request.json()

    async with async_session() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings_obj = result.scalar_one_or_none()

        api_key_raw = data.get("api_key", "")
        # If the key is masked (contains ****), keep the existing encrypted value
        if "****" in api_key_raw:
            encrypted_key = settings_obj.api_key if settings_obj else ""
        else:
            encrypted_key = encrypt_api_key(api_key_raw)

        if settings_obj:
            settings_obj.ai_provider = data.get("ai_provider", "")
            settings_obj.api_key = encrypted_key
            settings_obj.api_base_url = data.get("api_base_url", "")
            settings_obj.ai_model = data.get("ai_model", "")
            settings_obj.system_font = data.get("system_font", "")
            settings_obj.editor_font = data.get("editor_font", "")
        else:
            settings_obj = UserSettings(
                user_id=user.id,
                ai_provider=data.get("ai_provider", ""),
                api_key=encrypted_key,
                api_base_url=data.get("api_base_url", ""),
                ai_model=data.get("ai_model", ""),
                system_font=data.get("system_font", ""),
                editor_font=data.get("editor_font", ""),
            )
            db.add(settings_obj)

        await db.commit()

    return {"ok": True}
