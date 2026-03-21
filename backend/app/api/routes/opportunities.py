from fastapi import APIRouter

from app.api.schemas.trade import OpportunityItemDetail, OpportunityItemRow, SourceSummary, TradeRefreshState
from app.repositories.trade_repository import TradeRepository

router = APIRouter(prefix="/opportunities", tags=["trade"])


@router.get("/source-summaries", response_model=list[SourceSummary])
def get_source_summaries(target_location_id: int, period_days: int = 14) -> list[SourceSummary]:
    return TradeRepository().list_source_summaries(target_location_id, period_days)


@router.get("/items", response_model=list[OpportunityItemRow])
def get_items(target_location_id: int, source_location_id: int, period_days: int = 14) -> list[OpportunityItemRow]:
    return TradeRepository().list_items(target_location_id, source_location_id, period_days)


@router.get("/item-detail", response_model=OpportunityItemDetail)
def get_item_detail(
    target_location_id: int,
    source_location_id: int,
    type_id: int,
    period_days: int = 14,
) -> OpportunityItemDetail:
    return TradeRepository().get_item_detail(target_location_id, source_location_id, type_id, period_days)


@router.get("/refresh-state", response_model=TradeRefreshState)
def get_refresh_state() -> TradeRefreshState:
    return TradeRefreshState(last_refresh_at=TradeRepository().get_last_refresh())
