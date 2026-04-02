import { useQuery } from "@tanstack/react-query";

import { getDatabaseTable, getDatabaseTables } from "../api/database";
import type { DatabaseTableQuery } from "../types/database";

export function useDatabaseTables() {
  return useQuery({
    queryKey: ["databaseTables"],
    queryFn: getDatabaseTables,
    placeholderData: (previousData) => previousData,
    refetchInterval: 60_000,
  });
}

export function useDatabaseTable(tableName: string | null, query: DatabaseTableQuery) {
  return useQuery({
    queryKey: ["databaseTable", tableName, query],
    queryFn: () => getDatabaseTable(tableName ?? "", query),
    enabled: tableName !== null,
    placeholderData: (previousData) => previousData,
    refetchInterval: 60_000,
  });
}
