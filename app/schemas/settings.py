from pydantic import BaseModel


class UserSettingsSave(BaseModel):
    ai_provider: str = ""
    api_key: str = ""
    api_base_url: str = ""
    ai_model: str = ""
    system_font: str = ""
    editor_font: str = ""


class UserSettingsResponse(BaseModel):
    ai_provider: str
    api_key: str
    api_base_url: str
    ai_model: str
    system_font: str
    editor_font: str

    model_config = {"from_attributes": True}
