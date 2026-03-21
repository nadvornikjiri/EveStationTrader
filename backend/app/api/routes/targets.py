from fastapi import APIRouter

from app.api.schemas.trade import TargetLocation
from app.repositories.trade_repository import TradeRepository

router = APIRouter(tags=["trade"])


@router.get("/targets", response_model=list[TargetLocation])
def get_targets() -> list[TargetLocation]:
    return TradeRepository().list_targets()


@router.get("/sources", response_model=list[TargetLocation])
def get_sources(target_location_id: int, period_days: int = 14) -> list[TargetLocation]:
    return TradeRepository().list_sources(target_location_id, period_days)
