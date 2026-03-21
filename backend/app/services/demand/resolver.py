from app.domain.enums import DemandSource


def resolve_demand_source(
    target_location_type: str,
    observation_window_hours: float,
    snapshot_coverage_pct: float,
    fallback_value: float,
    local_value: float,
) -> tuple[DemandSource, float]:
    if target_location_type == "npc_station":
        return (DemandSource.ADAM4EVE, fallback_value)
    if observation_window_hours >= 72 and snapshot_coverage_pct >= 0.75:
        return (DemandSource.LOCAL_STRUCTURE, local_value)
    return (DemandSource.REGIONAL_FALLBACK, fallback_value)
