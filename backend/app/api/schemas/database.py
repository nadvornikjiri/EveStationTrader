from pydantic import BaseModel


class DatabaseTableSummary(BaseModel):
    name: str
    row_count: int


class DatabaseTableData(BaseModel):
    table_name: str
    columns: list[str]
    rows: list[dict[str, object | None]]
    row_count: int
    filtered_row_count: int
    page: int
    page_size: int
    total_pages: int
    sort_column: str | None
    sort_direction: str
    filter_text: str
