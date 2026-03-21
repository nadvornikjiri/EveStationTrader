from app.api.schemas.auth import CurrentUser
from app.services.auth.service import AuthService


def get_current_user() -> CurrentUser:
    return AuthService().get_current_user()
