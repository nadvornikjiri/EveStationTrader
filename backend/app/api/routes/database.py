from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import MetaData, Table, func, inspect, select

from app.api.schemas.database import DatabaseTableData, DatabaseTableSummary
from app.db.session import SessionLocal, engine
from app.models.all_models import Item, Location, Region, System

router = APIRouter(prefix="/database", tags=["database"])


@router.get("/tables", response_model=list[DatabaseTableSummary])
def list_database_tables() -> list[DatabaseTableSummary]:
    inspector = inspect(engine)
    session = SessionLocal()
    try:
        table_summaries: list[DatabaseTableSummary] = []
        for table_name in sorted(inspector.get_table_names()):
            table = Table(table_name, MetaData(), autoload_with=engine)
            row_count = session.execute(select(func.count()).select_from(table)).scalar_one()
            table_summaries.append(DatabaseTableSummary(name=table_name, row_count=row_count))
        return table_summaries
    finally:
        session.close()


@router.get("/tables/{table_name}", response_model=DatabaseTableData)
def get_database_table(
    table_name: str,
    limit: int = Query(default=200, ge=1, le=1000),
) -> DatabaseTableData:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail=f"Unknown table '{table_name}'.")

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    session = SessionLocal()
    try:
        row_count = session.execute(select(func.count()).select_from(table)).scalar_one()

        statement = select(table)
        primary_key_columns = list(table.primary_key.columns)
        if primary_key_columns:
            statement = statement.order_by(*[column.desc() for column in primary_key_columns])
        rows = [{key: _serialize_value(value) for key, value in row.items()} for row in session.execute(statement.limit(limit)).mappings().all()]
        columns, rows = _enrich_database_rows(session, table_name=table_name, columns=[column.name for column in table.columns], rows=rows)

        return DatabaseTableData(
            table_name=table_name,
            columns=columns,
            rows=rows,
            row_count=row_count,
            limit=limit,
        )
    finally:
        session.close()


def _serialize_value(value: object | None) -> object | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _enrich_database_rows(
    session,
    *,
    table_name: str,
    columns: list[str],
    rows: list[dict[str, object | None]],
) -> tuple[list[str], list[dict[str, object | None]]]:
    if table_name != "adam_market_orders_trade_raw" or not rows:
        return columns, rows

    location_ids = sorted(
        {
            int(location_id)
            for row in rows
            for location_id in [row.get("location_id")]
            if isinstance(location_id, int)
        }
    )
    type_ids = sorted(
        {
            int(type_id)
            for row in rows
            for type_id in [row.get("type_id")]
            if isinstance(type_id, int)
        }
    )

    locations = {
        row.eve_location_id: row
        for row in session.execute(
            select(
                Location.location_id.label("eve_location_id"),
                Location.name.label("location_name"),
                Region.name.label("region_name"),
                System.name.label("system_name"),
            )
            .outerjoin(Region, Region.id == Location.region_id)
            .outerjoin(System, System.id == Location.system_id)
            .where(Location.location_id.in_(location_ids))
        ).all()
    }
    items = {
        row.eve_type_id: row
        for row in session.execute(
            select(
                Item.type_id.label("eve_type_id"),
                Item.name.label("item_name"),
            ).where(Item.type_id.in_(type_ids))
        ).all()
    }

    enriched_rows: list[dict[str, object | None]] = []
    for row in rows:
        enriched_row = dict(row)
        location = locations.get(row.get("location_id"))
        item = items.get(row.get("type_id"))
        enriched_row["location_eve_id"] = getattr(location, "eve_location_id", None)
        enriched_row["location_name"] = getattr(location, "location_name", None)
        enriched_row["location_region"] = getattr(location, "region_name", None)
        enriched_row["location_system"] = getattr(location, "system_name", None)
        enriched_row["type_eve_id"] = getattr(item, "eve_type_id", None)
        enriched_row["item_name"] = getattr(item, "item_name", None)
        enriched_rows.append(enriched_row)

    enriched_columns = list(columns)
    if "location_id" in enriched_columns:
        location_index = enriched_columns.index("location_id") + 1
        enriched_columns[location_index:location_index] = [
            "location_eve_id",
            "location_name",
            "location_region",
            "location_system",
        ]
    else:
        enriched_columns.extend(["location_eve_id", "location_name", "location_region", "location_system"])

    if "type_id" in enriched_columns:
        type_index = enriched_columns.index("type_id") + 1
        enriched_columns[type_index:type_index] = ["type_eve_id", "item_name"]
    else:
        enriched_columns.extend(["type_eve_id", "item_name"])

    return enriched_columns, enriched_rows
