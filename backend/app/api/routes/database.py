from datetime import date, datetime
from decimal import Decimal
from math import ceil
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import MetaData, String, Table, and_, asc, cast, desc, func, inspect, or_, select
from sqlalchemy.sql import ColumnElement, Select

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
        column_filters = _extract_column_filters(request=request, selectable_columns=selectable_columns)
        if cleaned_filter_text:
            statement = statement.where(
                or_(*[cast(column, String).ilike(f"%{cleaned_filter_text}%") for column in selectable_columns.values()])
            )
        if column_filters:
            statement = statement.where(
                and_(
                    *[
                        cast(selectable_columns[column_name], String).ilike(f"%{filter_value}%")
                        for column_name, filter_value in column_filters.items()
                    ]
                )
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


def _build_database_statement(
    *,
    table_name: str,
    table: Table,
) -> tuple[Select[Any], list[str], dict[str, ColumnElement[Any]]]:
    selectable_columns: dict[str, ColumnElement[Any]] = {column.name: column for column in table.columns}

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
