from app.domain.enums import DemandSource
from app.services.demand.resolver import resolve_demand_source


def test_npc_targets_use_adam4eve() -> None:
    source, value = resolve_demand_source("npc_station", False, 9.0, 3.0)
    assert source == DemandSource.ADAM4EVE
    assert value == 9.0


def test_structure_fallback_when_local_value_is_missing() -> None:
    source, value = resolve_demand_source("structure", False, 9.0, 3.0)
    assert source == DemandSource.REGIONAL_FALLBACK
    assert value == 9.0


def test_structure_local_when_local_value_exists() -> None:
    source, value = resolve_demand_source("structure", True, 9.0, 3.0)
    assert source == DemandSource.LOCAL_STRUCTURE
    assert value == 3.0
