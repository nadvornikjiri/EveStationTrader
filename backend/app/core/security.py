from app.core.config import get_settings


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
