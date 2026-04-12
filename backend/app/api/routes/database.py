from datetime import date, datetime
from decimal import Decimal
from math import ceil
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import MetaData, String, Table, and_, asc, cast, desc, func, inspect, or_, select, text
from sqlalchemy.sql import ColumnElement, Select

from app.api.schemas.database import DatabaseTableData, DatabaseTableSummary
from app.db.session import SessionLocal, engine
from app.models.all_models import Item, Location, Region, System

router = APIRouter(prefix="/database", tags=["database"])


@router.get("/tables", response_model=list[DatabaseTableSummary])
def list_database_tables() -> list[DatabaseTableSummary]:
    inspector = inspect(engine)
    preparer = engine.dialect.identifier_preparer
    session = SessionLocal()
    try:
        table_summaries: list[DatabaseTableSummary] = []
        for table_name in sorted(inspector.get_table_names()):
            quoted_table_name = preparer.quote(table_name)
            row_count = session.execute(text(f"SELECT count(*) FROM {quoted_table_name}")).scalar_one()
            table_summaries.append(DatabaseTableSummary(name=table_name, row_count=row_count))
        return table_summaries
    finally:
        session.close()


@router.get("/tables/{table_name}", response_model=DatabaseTableData)
def get_database_table(
    request: Request,
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_column: str | None = Query(default=None),
    sort_direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    filter_text: str = Query(default="", max_length=200),
) -> DatabaseTableData:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail=f"Unknown table '{table_name}'.")

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    session = SessionLocal()
    try:
        row_count = session.execute(select(func.count()).select_from(table)).scalar_one()
        statement, columns, selectable_columns = _build_database_statement(table_name=table_name, table=table)
        cleaned_filter_text = filter_text.strip()
        column_filters = _extract_column_filters(
            table_name=table_name,
            request=request,
            selectable_columns=selectable_columns,
        )
        if cleaned_filter_text:
            statement = statement.where(
                or_(*[cast(column, String).ilike(f"%{cleaned_filter_text}%") for column in selectable_columns.values()])
            )
        if column_filters:
            statement = statement.where(
                and_(*_build_column_filter_clauses(
                    table_name=table_name,
                    column_filters=column_filters,
                    selectable_columns=selectable_columns,
                ))
            )
        filtered_row_count = session.execute(select(func.count()).select_from(statement.subquery())).scalar_one()

        resolved_sort_column, resolved_sort_direction = _resolve_sorting(
            columns=columns,
            selectable_columns=selectable_columns,
            requested_sort_column=sort_column,
            requested_sort_direction=sort_direction,
            primary_key_columns=[column.name for column in table.primary_key.columns],
        )
        ordered_statement = statement.order_by(
            _build_sort_expression(selectable_columns[resolved_sort_column], resolved_sort_direction),
            *_build_stable_tie_breakers(
                selectable_columns=selectable_columns,
                primary_key_columns=[column.name for column in table.primary_key.columns],
                sort_column=resolved_sort_column,
                sort_direction=resolved_sort_direction,
            ),
        )
        total_pages = max(ceil(filtered_row_count / page_size), 1)
        resolved_page = min(page, total_pages)
        offset = (resolved_page - 1) * page_size

        rows = [
            {key: _serialize_value(value) for key, value in row.items()}
            for row in session.execute(ordered_statement.limit(page_size).offset(offset)).mappings().all()
        ]

        return DatabaseTableData(
            table_name=table_name,
            columns=columns,
            rows=rows,
            row_count=row_count,
            filtered_row_count=filtered_row_count,
            page=resolved_page,
            page_size=page_size,
            total_pages=total_pages,
            sort_column=resolved_sort_column,
            sort_direction=resolved_sort_direction,
            filter_text=cleaned_filter_text,
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


def _extract_column_filters(
    *,
    table_name: str,
    request: Request,
    selectable_columns: dict[str, ColumnElement[Any]],
) -> dict[str, str]:
    column_filters: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if not key.startswith("filter_"):
            continue
        column_name = key.removeprefix("filter_")
        cleaned_value = value.strip()
        if cleaned_value and column_name in selectable_columns:
            column_filters[column_name] = cleaned_value
    return column_filters


def _build_column_filter_clauses(
    *,
    table_name: str,
    column_filters: dict[str, str],
    selectable_columns: dict[str, ColumnElement[Any]],
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    for column_name, filter_value in column_filters.items():
        if table_name == "opportunity_items" and column_name == "type_id" and "type_eve_id" in selectable_columns:
            clauses.append(
                or_(
                    cast(selectable_columns["type_id"], String).ilike(f"%{filter_value}%"),
                    cast(selectable_columns["type_eve_id"], String).ilike(f"%{filter_value}%"),
                )
            )
            continue
        clauses.append(cast(selectable_columns[column_name], String).ilike(f"%{filter_value}%"))
    return clauses


def _build_database_statement(
    *,
    table_name: str,
    table: Table,
) -> tuple[Select[Any], list[str], dict[str, ColumnElement[Any]]]:
    selectable_columns: dict[str, ColumnElement[Any]] = {column.name: column for column in table.columns}

    if table_name == "esi_history_daily":
        history_columns = [column for column in table.columns]
        region_eve_id = Region.region_id.label("region_eve_id")
        region_name = Region.name.label("region_name")
        type_eve_id = Item.type_id.label("type_eve_id")
        item_name = Item.name.label("item_name")
        statement = (
            select(
                *history_columns,
                region_eve_id,
                region_name,
                type_eve_id,
                item_name,
            )
            .select_from(table)
            .outerjoin(Region, Region.id == table.c.region_id)
            .outerjoin(Item, Item.id == table.c.type_id)
        )

        enriched_columns = [column.name for column in history_columns]
        if "region_id" in enriched_columns:
            region_index = enriched_columns.index("region_id") + 1
            enriched_columns[region_index:region_index] = ["region_eve_id", "region_name"]
        if "type_id" in enriched_columns:
            type_index = enriched_columns.index("type_id") + 1
            enriched_columns[type_index:type_index] = ["type_eve_id", "item_name"]

        selectable_columns.update(
            {
                "region_eve_id": region_eve_id,
                "region_name": region_name,
                "type_eve_id": type_eve_id,
                "item_name": item_name,
            }
        )
        return statement, enriched_columns, selectable_columns

    if table_name == "opportunity_items":
        opportunity_columns = [column for column in table.columns]
        type_eve_id = Item.type_id.label("type_eve_id")
        item_name = Item.name.label("item_name")

        target_location = Location.__table__.alias("target_location")
        source_location = Location.__table__.alias("source_location")

        statement = (
            select(
                *opportunity_columns,
                target_location.c.location_id.label("target_location_eve_id"),
                target_location.c.name.label("target_location_name"),
                source_location.c.location_id.label("source_location_eve_id"),
                source_location.c.name.label("source_location_name"),
                type_eve_id,
                item_name,
            )
            .select_from(table)
            .outerjoin(target_location, target_location.c.id == table.c.target_location_id)
            .outerjoin(source_location, source_location.c.id == table.c.source_location_id)
            .outerjoin(Item, Item.id == table.c.type_id)
        )

        enriched_columns = [column.name for column in opportunity_columns]
        if "target_location_id" in enriched_columns:
            target_index = enriched_columns.index("target_location_id") + 1
            enriched_columns[target_index:target_index] = ["target_location_eve_id", "target_location_name"]
        if "source_location_id" in enriched_columns:
            source_index = enriched_columns.index("source_location_id") + 1
            enriched_columns[source_index:source_index] = ["source_location_eve_id", "source_location_name"]
        if "type_id" in enriched_columns:
            type_index = enriched_columns.index("type_id") + 1
            enriched_columns[type_index:type_index] = ["type_eve_id", "item_name"]

        selectable_columns.update(
            {
                "target_location_eve_id": target_location.c.location_id.label("target_location_eve_id"),
                "target_location_name": target_location.c.name.label("target_location_name"),
                "source_location_eve_id": source_location.c.location_id.label("source_location_eve_id"),
                "source_location_name": source_location.c.name.label("source_location_name"),
                "type_eve_id": type_eve_id,
                "item_name": item_name,
            }
        )
        return statement, enriched_columns, selectable_columns

    if table_name != "adam_market_orders_trade_raw":
        return select(*table.columns), [column.name for column in table.columns], selectable_columns

    adam_columns = [column for column in table.columns]
    location_eve_id = Location.location_id.label("location_eve_id")
    location_name = Location.name.label("location_name")
    location_region = Region.name.label("location_region")
    location_system = System.name.label("location_system")
    type_eve_id = Item.type_id.label("type_eve_id")
    item_name = Item.name.label("item_name")
    statement = (
        select(
            *adam_columns,
            location_eve_id,
            location_name,
            location_region,
            location_system,
            type_eve_id,
            item_name,
        )
        .select_from(table)
        .outerjoin(Location, Location.location_id == table.c.location_id)
        .outerjoin(Region, Region.id == Location.region_id)
        .outerjoin(System, System.id == Location.system_id)
        .outerjoin(Item, Item.type_id == table.c.type_id)
    )

    enriched_columns = [column.name for column in adam_columns]
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

    selectable_columns.update(
        {
            "location_eve_id": location_eve_id,
            "location_name": location_name,
            "location_region": location_region,
            "location_system": location_system,
            "type_eve_id": type_eve_id,
            "item_name": item_name,
        }
    )
    return statement, enriched_columns, selectable_columns


def _resolve_sorting(
    *,
    columns: list[str],
    selectable_columns: dict[str, ColumnElement[Any]],
    requested_sort_column: str | None,
    requested_sort_direction: str,
    primary_key_columns: list[str],
) -> tuple[str, str]:
    if requested_sort_column in selectable_columns:
        resolved_sort_column = requested_sort_column
        resolved_sort_direction = requested_sort_direction
    elif primary_key_columns:
        resolved_sort_column = primary_key_columns[0]
        resolved_sort_direction = "desc"
    else:
        resolved_sort_column = columns[0]
        resolved_sort_direction = "asc"
    return resolved_sort_column, resolved_sort_direction


def _build_sort_expression(column: ColumnElement[Any], direction: str) -> ColumnElement[Any]:
    return asc(column).nulls_last() if direction == "asc" else desc(column).nulls_last()


def _build_stable_tie_breakers(
    *,
    selectable_columns: dict[str, ColumnElement[Any]],
    primary_key_columns: list[str],
    sort_column: str,
    sort_direction: str,
) -> list[ColumnElement[Any]]:
    tie_breakers: list[ColumnElement[Any]] = []
    for primary_key in primary_key_columns:
        if primary_key == sort_column or primary_key not in selectable_columns:
            continue
        tie_breakers.append(_build_sort_expression(selectable_columns[primary_key], sort_direction))
    return tie_breakers
