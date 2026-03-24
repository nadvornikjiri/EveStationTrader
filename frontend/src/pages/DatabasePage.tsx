import { useEffect, useMemo, useState } from "react";

import { useDatabaseTable, useDatabaseTables } from "../hooks/useDatabaseData";

type SortDirection = "asc" | "desc";

function stringifyValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function compareValues(left: unknown, right: unknown) {
  if (left === right) {
    return 0;
  }
  if (left === null || left === undefined) {
    return 1;
  }
  if (right === null || right === undefined) {
    return -1;
  }
  if (typeof left === "number" && typeof right === "number") {
    return left - right;
  }
  return stringifyValue(left).localeCompare(stringifyValue(right), undefined, { numeric: true });
}

export function DatabasePage() {
  const tables = useDatabaseTables();
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const tableData = useDatabaseTable(selectedTable);

  useEffect(() => {
    if (selectedTable === null && (tables.data?.length ?? 0) > 0) {
      setSelectedTable(tables.data?.[0].name ?? null);
    }
  }, [selectedTable, tables.data]);

  useEffect(() => {
    const firstColumn = tableData.data?.columns[0] ?? null;
    if (sortColumn === null && firstColumn !== null) {
      setSortColumn(firstColumn);
      setSortDirection("asc");
    }
  }, [sortColumn, tableData.data?.columns]);

  const sortedRows = useMemo(() => {
    const rows = tableData.data?.rows ?? [];
    if (sortColumn === null) {
      return rows;
    }

    const sorted = [...rows].sort((left, right) => compareValues(left[sortColumn], right[sortColumn]));
    return sortDirection === "asc" ? sorted : sorted.reverse();
  }, [sortColumn, sortDirection, tableData.data?.rows]);

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection("asc");
  };

  const tableStatusMessage = tables.error
    ? "Database table list is temporarily unavailable."
    : tableData.error
      ? "Selected table is temporarily unavailable."
      : tableData.data
        ? `Showing ${sortedRows.length} of ${tableData.data.row_count} rows from ${tableData.data.table_name}.`
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
              setSelectedTable(event.target.value);
              setSortColumn(null);
            }}
          >
            {(tables.data ?? []).map((table) => (
              <option key={table.name} value={table.name}>
                {table.name}
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
          <div className="table-scroll">
            <table className="data-table database-table">
              <thead>
                <tr>
                  {tableData.data.columns.map((column) => (
                    <th key={column}>
                      <button className="sort-button" onClick={() => handleSort(column)} type="button">
                        {column}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, index) => (
                  <tr key={`${tableData.data?.table_name ?? "table"}-${index}`}>
                    {tableData.data.columns.map((column) => (
                      <td key={`${index}-${column}`}>{stringifyValue(row[column]) || "-"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
