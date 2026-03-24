from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import MetaData, Table, func, inspect, select

from app.api.schemas.database import DatabaseTableData, DatabaseTableSummary
from app.db.session import SessionLocal, engine

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
        rows = session.execute(statement.limit(limit)).mappings().all()

        return DatabaseTableData(
            table_name=table_name,
            columns=[column.name for column in table.columns],
            rows=[{key: _serialize_value(value) for key, value in row.items()} for row in rows],
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
