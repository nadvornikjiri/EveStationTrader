from fastapi import APIRouter, HTTPException

from app.api.schemas.trade import (
    InTransitAssetRecord,
    InTransitAssetUpsertRequest,
    OpportunityItemDetail,
    OpportunityItemRow,
    SourceSummary,
    TargetOpportunityItemRow,
    TradeRefreshState,
)
from app.repositories.trade_repository import TradeRepository

router = APIRouter(prefix="/opportunities", tags=["trade"])


@router.get("/source-summaries", response_model=list[SourceSummary])
def get_source_summaries(
    target_location_id: int,
    period_days: int = 14,
    item_search: str = "",
    min_profit: float = 0.0,
    min_roi_now_pct: float = 0.0,
    min_demand_day: float = 0.0,
    max_dos: float | None = None,
    max_item_volume_m3: float | None = None,
    source_type: str = "all",
    min_security: str = "all",
    demand_source: str = "all",
    min_esi_demand_day: float = 0.0,
) -> list[SourceSummary]:
    return TradeRepository().list_source_summaries(
        target_location_id,
        period_days,
        item_search=item_search,
        min_profit=min_profit,
        min_roi_now_pct=min_roi_now_pct,
        min_demand_day=min_demand_day,
        max_dos=max_dos,
        max_item_volume_m3=max_item_volume_m3,
        source_type=source_type,
        min_security=min_security,
        demand_source=demand_source,
        min_esi_demand_day=min_esi_demand_day,
    )


@router.get("/items", response_model=list[OpportunityItemRow])
def get_items(
    target_location_id: int,
    source_location_id: int,
    period_days: int = 14,
    item_search: str = "",
    min_profit: float = 0.0,
    min_roi_now_pct: float = 0.0,
    min_demand_day: float = 0.0,
    max_dos: float | None = None,
    max_item_volume_m3: float | None = None,
    source_type: str = "all",
    min_security: str = "all",
    demand_source: str = "all",
    min_esi_demand_day: float = 0.0,
) -> list[OpportunityItemRow]:
    return TradeRepository().list_items(
        target_location_id,
        source_location_id,
        period_days,
        item_search=item_search,
        min_profit=min_profit,
        min_roi_now_pct=min_roi_now_pct,
        min_demand_day=min_demand_day,
        max_dos=max_dos,
        max_item_volume_m3=max_item_volume_m3,
        source_type=source_type,
        min_security=min_security,
        demand_source=demand_source,
        min_esi_demand_day=min_esi_demand_day,
    )


@router.get("/target-items", response_model=list[TargetOpportunityItemRow])
def get_target_items(target_location_id: int, period_days: int = 14) -> list[TargetOpportunityItemRow]:
    return TradeRepository().list_target_items(target_location_id, period_days)


@router.get("/item-detail", response_model=OpportunityItemDetail)
def get_item_detail(
    target_location_id: int,
    source_location_id: int,
    type_id: int,
    period_days: int = 14,
) -> OpportunityItemDetail:
    try:
        return TradeRepository().get_item_detail(target_location_id, source_location_id, type_id, period_days)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/refresh-state", response_model=TradeRefreshState)
def get_refresh_state() -> TradeRefreshState:
    return TradeRefreshState(last_refresh_at=TradeRepository().get_last_refresh())


@router.post("/refresh", response_model=TradeRefreshState)
def refresh_trade_opportunities(target_location_id: int, period_days: int = 14) -> TradeRefreshState:
    repository = TradeRepository()
    try:
        repository.refresh_opportunities(target_location_id, period_days)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TradeRefreshState(last_refresh_at=repository.get_last_refresh())


@router.get("/in-transit", response_model=list[InTransitAssetRecord])
def get_in_transit_assets(target_location_id: int) -> list[InTransitAssetRecord]:
    return TradeRepository().list_in_transit_assets(target_location_id)


@router.post("/in-transit", response_model=InTransitAssetRecord)
def upsert_in_transit_asset(payload: InTransitAssetUpsertRequest) -> InTransitAssetRecord:
    try:
        return TradeRepository().upsert_in_transit_asset(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/in-transit/{entry_id}", status_code=204)
def delete_in_transit_asset(entry_id: int) -> None:
    deleted = TradeRepository().delete_in_transit_asset(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"In-transit entry {entry_id} was not found.")
