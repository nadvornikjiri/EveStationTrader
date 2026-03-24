export type DatabaseTableSummary = {
  name: string;
  row_count: number;
};

export type DatabaseTableData = {
  table_name: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  limit: number;
};
