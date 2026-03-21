from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.characters import router as characters_router
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.settings import router as settings_router
from app.api.routes.sync import router as sync_router
from app.api.routes.targets import router as targets_router

router = APIRouter()
router.include_router(targets_router)
router.include_router(opportunities_router)
router.include_router(sync_router)
router.include_router(characters_router)
router.include_router(auth_router)
router.include_router(settings_router)
