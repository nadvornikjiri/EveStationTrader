from pydantic import BaseModel


class DatabaseTableSummary(BaseModel):
    name: str
    row_count: int


class DatabaseTableData(BaseModel):
    table_name: str
    columns: list[str]
    rows: list[dict[str, object | None]]
    row_count: int
    limit: int
