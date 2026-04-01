from app.domain.enums import DemandSource


def resolve_demand_source(
    target_location_type: str,
    has_local_value: bool,
    fallback_value: float,
    local_value: float,
) -> tuple[DemandSource, float]:
    if target_location_type == "npc_station":
        return (DemandSource.ADAM4EVE, fallback_value)
    if has_local_value:
        return (DemandSource.LOCAL_STRUCTURE, local_value)
    return (DemandSource.REGIONAL_FALLBACK, fallback_value)
