import { useQuery } from "@tanstack/react-query";

import { getDatabaseTable, getDatabaseTables } from "../api/database";

export function useDatabaseTables() {
  return useQuery({
    queryKey: ["databaseTables"],
    queryFn: getDatabaseTables,
    placeholderData: (previousData) => previousData,
    refetchInterval: 60_000,
  });
}

export function useDatabaseTable(tableName: string | null, limit = 200) {
  return useQuery({
    queryKey: ["databaseTable", tableName, limit],
    queryFn: () => getDatabaseTable(tableName ?? "", limit),
    enabled: tableName !== null,
    placeholderData: (previousData) => previousData,
    refetchInterval: 60_000,
  });
}
