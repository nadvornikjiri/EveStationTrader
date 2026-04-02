import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnFiltersState,
  type ColumnDef,
  type PaginationState,
  type SortingState,
} from "@tanstack/react-table";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";

import { useDatabaseTable, useDatabaseTables } from "../hooks/useDatabaseData";
import type { DatabaseTableQuery } from "../types/database";

function stringifyValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

const DEFAULT_PAGE_SIZE = 50;
const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

export function DatabasePage() {
  const tables = useDatabaseTables();
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [filterInput, setFilterInput] = useState("");
  const deferredFilterInput = useDeferredValue(filterInput);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const deferredColumnFilters = useDeferredValue(columnFilters);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: DEFAULT_PAGE_SIZE,
  });
  const query = useMemo<DatabaseTableQuery>(
    () => ({
      page: pagination.pageIndex + 1,
      pageSize: pagination.pageSize,
      sortColumn: sorting[0]?.id ?? null,
      sortDirection: sorting[0]?.desc ? "desc" : "asc",
      filterText: deferredFilterInput.trim(),
      columnFilters: Object.fromEntries(
        deferredColumnFilters
          .map((filter) => [filter.id, String(filter.value).trim()])
          .filter(([, value]) => value.length > 0),
      ),
    }),
    [deferredColumnFilters, deferredFilterInput, pagination.pageIndex, pagination.pageSize, sorting],
  );
  const tableData = useDatabaseTable(selectedTable, query);

  useEffect(() => {
    if (selectedTable === null && (tables.data?.length ?? 0) > 0) {
      setSelectedTable(tables.data?.[0].name ?? null);
    }
  }, [selectedTable, tables.data]);

  useEffect(() => {
    const resolvedPageIndex = (tableData.data?.page ?? 1) - 1;
    if (resolvedPageIndex !== pagination.pageIndex) {
      setPagination((currentPagination) => ({
        ...currentPagination,
        pageIndex: resolvedPageIndex,
      }));
    }
  }, [pagination.pageIndex, tableData.data?.page]);

  useEffect(() => {
    const resolvedSortColumn = tableData.data?.sort_column ?? null;
    const resolvedSortDirection = tableData.data?.sort_direction ?? "asc";
    const nextSorting: SortingState =
      resolvedSortColumn === null
        ? []
        : [
            {
              id: resolvedSortColumn,
              desc: resolvedSortDirection === "desc",
            },
          ];
    const sortingChanged =
      nextSorting.length !== sorting.length ||
      nextSorting.some((entry, index) => entry.id !== sorting[index]?.id || entry.desc !== sorting[index]?.desc);
    if (sortingChanged) {
      setSorting(nextSorting);
    }
  }, [sorting, tableData.data?.sort_column, tableData.data?.sort_direction]);

  const columns = useMemo<ColumnDef<Record<string, unknown>>[]>(
    () =>
      (tableData.data?.columns ?? []).map((column) => ({
        accessorKey: column,
        id: column,
        header: column,
        cell: ({ getValue }) => stringifyValue(getValue()) || "-",
      })),
    [tableData.data?.columns],
  );

  const table = useReactTable({
    data: tableData.data?.rows ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualFiltering: true,
    manualPagination: true,
    manualSorting: true,
    pageCount: tableData.data?.total_pages ?? 1,
    state: {
      columnFilters,
      pagination,
      sorting,
    },
    onColumnFiltersChange: (updater) => {
      startTransition(() => {
        const nextFilters = typeof updater === "function" ? updater(columnFilters) : updater;
        setColumnFilters(nextFilters);
        setPagination((currentPagination) => ({
          ...currentPagination,
          pageIndex: 0,
        }));
      });
    },
    onPaginationChange: setPagination,
    onSortingChange: (updater) => {
      startTransition(() => {
        const nextSorting = typeof updater === "function" ? updater(sorting) : updater;
        setSorting(nextSorting.slice(0, 1));
        setPagination((currentPagination) => ({
          ...currentPagination,
          pageIndex: 0,
        }));
      });
    },
  });

  const tableStatusMessage = tables.error
    ? "Database table list is temporarily unavailable."
    : tableData.error
      ? "Selected table is temporarily unavailable."
      : tableData.data
        ? `Showing ${tableData.data.rows.length} rows on page ${tableData.data.page} of ${tableData.data.total_pages}. ${tableData.data.filtered_row_count} matching rows out of ${tableData.data.row_count} total in ${tableData.data.table_name}.`
        : "Pick a table to inspect current database rows.";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Diagnostics</span>
          <h1>Database</h1>
        </div>
      </header>

      <section className="panel controls-grid database-controls-grid">
        <label>
          <span>Table</span>
          <select
            aria-label="Database Table"
            disabled={(tables.data?.length ?? 0) === 0}
            value={selectedTable ?? ""}
            onChange={(event) => {
              startTransition(() => {
                setSelectedTable(event.target.value);
                setFilterInput("");
                setSorting([]);
                setColumnFilters([]);
                setPagination({
                  pageIndex: 0,
                  pageSize: pagination.pageSize,
                });
              });
            }}
          >
            {(tables.data ?? []).map((tableSummary) => (
              <option key={tableSummary.name} value={tableSummary.name}>
                {tableSummary.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Filter Rows</span>
          <input
            aria-label="Filter Rows"
            placeholder="Search across visible columns"
            value={filterInput}
            onChange={(event) => {
              startTransition(() => {
                setFilterInput(event.target.value);
                setPagination((currentPagination) => ({
                  ...currentPagination,
                  pageIndex: 0,
                }));
              });
            }}
          />
        </label>
        <label>
          <span>Rows Per Page</span>
          <select
            aria-label="Rows Per Page"
            value={pagination.pageSize}
            onChange={(event) => {
              const nextPageSize = Number.parseInt(event.target.value, 10);
              startTransition(() => {
                setPagination({
                  pageIndex: 0,
                  pageSize: Number.isFinite(nextPageSize) ? nextPageSize : DEFAULT_PAGE_SIZE,
                });
              });
            }}
          >
            {PAGE_SIZE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <div className="trade-filter-note" role="status">
          {tableStatusMessage}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Rows</h2>
          <span>{tableData.isLoading ? "Loading..." : selectedTable ?? "No table selected"}</span>
        </div>
        {tables.error ? (
          <p className="detail-empty">Could not load database tables right now.</p>
        ) : tableData.error ? (
          <p className="detail-empty">Could not load the selected table right now.</p>
        ) : tableData.isLoading ? (
          <p className="detail-empty">Loading table data...</p>
        ) : tableData.data === undefined ? (
          <p className="detail-empty">No table selected.</p>
        ) : (
          <>
            <div className="table-scroll">
              <table className="data-table database-table">
                <thead>
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => {
                        const sortedState = header.column.getIsSorted();
                        return (
                          <th key={header.id}>
                            <button
                              className="sort-button"
                              onClick={header.column.getToggleSortingHandler()}
                              type="button"
                            >
                              {flexRender(header.column.columnDef.header, header.getContext())}
                              {sortedState === "asc" ? " ^" : sortedState === "desc" ? " v" : ""}
                            </button>
                          </th>
                        );
                      })}
                    </tr>
                  ))}
                  <tr>
                    {table.getAllLeafColumns().map((column) => (
                      <th key={`${column.id}-filter`}>
                        <input
                          aria-label={`Filter ${column.id}`}
                          className="database-column-filter"
                          placeholder={`Filter ${column.id}`}
                          value={String(column.getFilterValue() ?? "")}
                          onChange={(event) => {
                            column.setFilterValue(event.target.value);
                          }}
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row) => (
                    <tr key={row.id}>
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="panel pagination-panel database-pagination-panel" aria-label="Database table pagination">
              <span>
                Page {tableData.data.page} of {tableData.data.total_pages}
              </span>
              <div className="pagination-controls">
                <button
                  type="button"
                  className="inline-more-button"
                  disabled={tableData.data.page <= 1}
                  onClick={() => {
                    table.firstPage();
                  }}
                >
                  First
                </button>
                <button
                  type="button"
                  className="inline-more-button"
                  disabled={tableData.data.page <= 1}
                  onClick={() => {
                    table.previousPage();
                  }}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="inline-more-button"
                  disabled={tableData.data.page >= tableData.data.total_pages}
                  onClick={() => {
                    table.nextPage();
                  }}
                >
                  Next
                </button>
                <button
                  type="button"
                  className="inline-more-button"
                  disabled={tableData.data.page >= tableData.data.total_pages}
                  onClick={() => {
                    table.setPageIndex(Math.max(tableData.data.total_pages - 1, 0));
                  }}
                >
                  Last
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
