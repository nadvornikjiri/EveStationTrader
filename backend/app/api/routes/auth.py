import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.api.deps.auth import get_current_user
from app.api.schemas.auth import AuthRedirectResponse, CurrentUser
from app.api.schemas.common import MessageResponse
from app.core.config import get_settings
from app.core.security import (
    build_esi_scopes,
    generate_pkce,
    generate_state,
    get_auth_redirect_config,
    pop_pkce_verifier,
    store_pkce_verifier,
    verify_state,
)
from app.services.auth.service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def build_login_redirect_response() -> AuthRedirectResponse:
    params = get_auth_redirect_config()
    state = generate_state()
    code_verifier, code_challenge = generate_pkce()
    store_pkce_verifier(state, code_verifier)
    authorize_url = (
        "https://login.eveonline.com/v2/oauth/authorize/?"
        + urlencode({
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            **params,
        })
    )
    return AuthRedirectResponse(authorize_url=authorize_url, scopes=build_esi_scopes())


@router.get("/login", response_model=AuthRedirectResponse)
def login() -> AuthRedirectResponse:
    return build_login_redirect_response()


@router.get("/callback")
def callback(code: str | None = None, state: str | None = None) -> RedirectResponse:
    settings = get_settings()
    frontend_url = settings.frontend_url.rstrip("/")

    if not state or not verify_state(state):
        return RedirectResponse(url=f"{frontend_url}/characters?error=invalid_state")
    if not code:
        return RedirectResponse(url=f"{frontend_url}/characters?error=no_code")

    code_verifier = pop_pkce_verifier(state)
    if not code_verifier:
        return RedirectResponse(url=f"{frontend_url}/characters?error=missing_pkce")

    try:
        AuthService().handle_callback(code, code_verifier=code_verifier)
    except Exception as exc:
        import traceback
        print(f"SSO CALLBACK ERROR: {exc}", flush=True)
        traceback.print_exc()
        return RedirectResponse(url=f"{frontend_url}/characters?error=auth_failed")

    return RedirectResponse(url=f"{frontend_url}/characters?auth=success")


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout() -> MessageResponse:
    return MessageResponse(message="Logged out.")
