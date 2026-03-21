from urllib.parse import urlencode

from fastapi import APIRouter, Depends

from app.api.deps.auth import get_current_user
from app.api.schemas.auth import AuthRedirectResponse, CurrentUser
from app.api.schemas.common import MessageResponse
from app.core.security import build_esi_scopes, get_auth_redirect_config
from app.services.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_model=AuthRedirectResponse)
def login() -> AuthRedirectResponse:
    params = get_auth_redirect_config()
    authorize_url = f"https://login.eveonline.com/v2/oauth/authorize/?{urlencode({'response_type': 'code', **params})}"
    return AuthRedirectResponse(authorize_url=authorize_url, scopes=build_esi_scopes())


@router.get("/callback", response_model=CurrentUser | MessageResponse)
def callback(code: str | None = None) -> CurrentUser | MessageResponse:
    if not code:
        return MessageResponse(message="No EVE SSO code provided.")
    return AuthService().handle_callback(code)


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout() -> MessageResponse:
    return MessageResponse(message="Logged out.")
