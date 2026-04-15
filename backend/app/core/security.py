import hashlib
import hmac
import secrets

from app.core.config import get_settings


def generate_state() -> str:
    """Generate a self-verifying HMAC-signed state token for OAuth CSRF protection."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    sig = hmac.new(settings.esi_client_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def verify_state(state: str) -> bool:
    """Verify that a state token was issued by us (HMAC signature check)."""
    settings = get_settings()
    parts = state.split(".", 1)
    if len(parts) != 2:
        return False
    token, provided_sig = parts
    expected_sig = hmac.new(settings.esi_client_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, provided_sig)


def build_esi_scopes() -> list[str]:
    # Verified against current ESI scope set; keep this small until each sync
    # feature is fully implemented.
    return [
        "publicData",
        "esi-assets.read_assets.v1",
        "esi-markets.read_character_orders.v1",
        "esi-skills.read_skills.v1",
        "esi-universe.read_structures.v1",
    ]


def get_auth_redirect_config() -> dict[str, str]:
    settings = get_settings()
    return {
        "client_id": settings.esi_client_id,
        "redirect_uri": settings.esi_callback_url,
        "scope": " ".join(build_esi_scopes()),
    }
