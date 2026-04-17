import base64
import hashlib
import hmac
import secrets

from app.core.config import get_settings

# In-memory PKCE store: state -> code_verifier (single-user MVP)
_pkce_store: dict[str, str] = {}


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


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def store_pkce_verifier(state: str, code_verifier: str) -> None:
    """Store PKCE verifier for retrieval during callback."""
    _pkce_store[state] = code_verifier
    # Keep store small — evict old entries
    if len(_pkce_store) > 50:
        oldest = list(_pkce_store.keys())[0]
        del _pkce_store[oldest]


def pop_pkce_verifier(state: str) -> str | None:
    """Retrieve and remove PKCE verifier for the given state."""
    return _pkce_store.pop(state, None)


def build_esi_scopes() -> list[str]:
    # Verified against current ESI scope set; keep this small until each sync
    # feature is fully implemented.
    return [
        "esi-assets.read_assets.v1",
        "esi-markets.read_character_orders.v1",
        "esi-markets.structure_markets.v1",
        "esi-skills.read_skills.v1",
        "esi-skills.read_skillqueue.v1",
        "esi-structures.read_character.v1",
        "esi-structures.read_corporation.v1",
        "esi-universe.read_structures.v1",
        "esi-wallet.read_character_wallet.v1",
    ]


def get_auth_redirect_config() -> dict[str, str]:
    settings = get_settings()
    return {
        "client_id": settings.esi_client_id,
        "redirect_uri": settings.esi_callback_url,
        "scope": " ".join(build_esi_scopes()),
    }
