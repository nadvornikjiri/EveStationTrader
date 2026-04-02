export type DatabaseTableSummary = {
  name: string;
  row_count: number;
};

export type DatabaseTableQuery = {
  page: number;
  pageSize: number;
  sortColumn: string | null;
  sortDirection: "asc" | "desc";
  filterText: string;
  columnFilters: Record<string, string>;
};

export type DatabaseTableData = {
  table_name: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  filtered_row_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  sort_column: string | null;
  sort_direction: "asc" | "desc";
  filter_text: string;
};
