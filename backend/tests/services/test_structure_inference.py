from app.models.all_models import StructureSnapshotOrder
from app.services.structures.inference import compute_order_delta


def test_compute_order_delta_for_sell_order_reduction() -> None:
    previous = StructureSnapshotOrder(
        snapshot_id=1,
        structure_id=2,
        type_id=34,
        order_id=77,
        is_buy_order=False,
        price=100.0,
        volume_remain=50,
        issued=None,
        duration=None,
    )
    current = StructureSnapshotOrder(
        snapshot_id=2,
        structure_id=2,
        type_id=34,
        order_id=77,
        is_buy_order=False,
        price=100.0,
        volume_remain=20,
        issued=None,
        duration=None,
    )
    delta = compute_order_delta(previous, current)
    assert delta["delta_volume"] == -30
    assert delta["inferred_trade_units"] == 30
    assert delta["inferred_trade_side"] == "buy_from_sell"
