import { apiGet } from "./client";
import type { DatabaseTableData, DatabaseTableQuery, DatabaseTableSummary } from "../types/database";

export function getDatabaseTables() {
  return apiGet<DatabaseTableSummary[]>("/database/tables");
}

export function getDatabaseTable(tableName: string, query: DatabaseTableQuery) {
  const searchParams = new URLSearchParams({
    page: `${query.page}`,
    page_size: `${query.pageSize}`,
    sort_direction: query.sortDirection,
    filter_text: query.filterText,
  });
  if (query.sortColumn !== null) {
    searchParams.set("sort_column", query.sortColumn);
  }
  Object.entries(query.columnFilters).forEach(([column, value]) => {
    if (value.trim()) {
      searchParams.set(`filter_${column}`, value);
    }
  });
  return apiGet<DatabaseTableData>(`/database/tables/${tableName}?${searchParams.toString()}`);
}
