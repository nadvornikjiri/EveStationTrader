from app.models.all_models import StructureSnapshotOrder


def compute_order_delta(previous: StructureSnapshotOrder, current: StructureSnapshotOrder) -> dict:
    delta = current.volume_remain - previous.volume_remain
    inferred_units = abs(delta) if delta < 0 else 0
    return {
        "structure_id": current.structure_id,
        "type_id": current.type_id,
        "order_id": current.order_id,
        "old_volume": previous.volume_remain,
        "new_volume": current.volume_remain,
        "delta_volume": delta,
        "disappeared": False,
        "inferred_trade_side": "buy_from_sell" if not current.is_buy_order and delta < 0 else "sell_to_buy",
        "inferred_trade_units": inferred_units,
        "price": current.price,
    }
