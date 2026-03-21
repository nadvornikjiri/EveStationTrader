from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: int
    primary_character_id: int | None = None
    character_name: str | None = None
    is_authenticated: bool = False


class AuthRedirectResponse(BaseModel):
    authorize_url: str
    scopes: list[str]
