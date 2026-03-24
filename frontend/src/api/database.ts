import { apiGet } from "./client";
import type { DatabaseTableData, DatabaseTableSummary } from "../types/database";

export function getDatabaseTables() {
  return apiGet<DatabaseTableSummary[]>("/database/tables");
}

export function getDatabaseTable(tableName: string, limit = 200) {
  return apiGet<DatabaseTableData>(`/database/tables/${tableName}?limit=${limit}`);
}
