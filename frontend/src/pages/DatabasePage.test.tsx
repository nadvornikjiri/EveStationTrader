import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { DatabasePage } from "./DatabasePage";
import type { DatabaseTableQuery } from "../types/database";

const mockTablesState = vi.hoisted(() => ({
  data: [
    { name: "items", row_count: 2 },
    { name: "locations", row_count: 3 },
  ],
  error: null as Error | null,
}));

const mockUseDatabaseTable = vi.hoisted(() => vi.fn());

vi.mock("../hooks/useDatabaseData", () => ({
  useDatabaseTables: () => mockTablesState,
  useDatabaseTable: (...args: [string | null, DatabaseTableQuery]) => mockUseDatabaseTable(...args),
}));

function configureDatabaseTableMock() {
  mockUseDatabaseTable.mockReset();
  mockUseDatabaseTable.mockImplementation((_tableName: string | null, query: DatabaseTableQuery) => {
    const filterText = query.filterText.toLowerCase();
    const filteredRows = [
      { id: 1, type_id: 34, name: "Tritanium" },
      { id: 2, type_id: 35, name: "Pyerite" },
      { id: 3, type_id: 36, name: "Mexallon" },
    ]
      .filter((row) => row.name.toLowerCase().includes(filterText))
      .filter((row) =>
        Object.entries(query.columnFilters).every(([column, value]) =>
          String(row[column as keyof typeof row]).toLowerCase().includes(value.toLowerCase()),
        ),
      );
    const sortedRows = [...filteredRows].sort((left, right) => left.name.localeCompare(right.name));
    if (query.sortDirection === "desc") {
      sortedRows.reverse();
    }
    const start = (query.page - 1) * query.pageSize;
    const rows = sortedRows.slice(start, start + query.pageSize);
    const totalPages = Math.max(Math.ceil(filteredRows.length / query.pageSize), 1);
    return {
      isLoading: false,
      error: null,
      data: {
        table_name: "items",
        columns: ["id", "type_id", "name"],
        rows,
        row_count: 3,
        filtered_row_count: filteredRows.length,
        page: Math.min(query.page, totalPages),
        page_size: query.pageSize,
        total_pages: totalPages,
        sort_column: query.sortColumn ?? "id",
        sort_direction: query.sortColumn === null ? "desc" : query.sortDirection,
        filter_text: query.filterText,
      },
    };
  });
}

beforeEach(() => {
  mockTablesState.data = [
    { name: "items", row_count: 2 },
    { name: "locations", row_count: 3 },
  ];
  mockTablesState.error = null;
  configureDatabaseTableMock();
});

afterEach(() => {
  mockUseDatabaseTable.mockReset();
});

test("renders database browser with rows", () => {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DatabasePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(screen.getByText("Database")).toBeInTheDocument();
  expect(screen.getByLabelText("Database Table")).toBeInTheDocument();
  expect(screen.getByLabelText("Filter Rows")).toBeInTheDocument();
  expect(screen.getByLabelText("Rows Per Page")).toBeInTheDocument();
  expect(screen.getByLabelText("Filter name")).toBeInTheDocument();
  expect(screen.getByText("Tritanium")).toBeInTheDocument();
  expect(screen.getByText("Pyerite")).toBeInTheDocument();
});

test("applies filtering and pagination through the database query hook", async () => {
  const user = userEvent.setup();
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DatabasePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await user.selectOptions(screen.getByLabelText("Rows Per Page"), "25");
  await user.type(screen.getByLabelText("Filter Rows"), "py");
  await user.click(screen.getByRole("button", { name: "name" }));

  const latestCall = mockUseDatabaseTable.mock.calls[mockUseDatabaseTable.mock.calls.length - 1] as [
    string | null,
    DatabaseTableQuery,
  ];
  expect(latestCall[0]).toBe("items");
  expect(latestCall[1]).toMatchObject({
    page: 1,
    pageSize: 25,
    sortColumn: "name",
    sortDirection: "asc",
    filterText: "py",
    columnFilters: {},
  });
  expect(screen.getByText("Pyerite")).toBeInTheDocument();
  expect(screen.queryByText("Tritanium")).not.toBeInTheDocument();
});

test("applies per-column filtering through the database query hook", async () => {
  const user = userEvent.setup();
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DatabasePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await user.type(screen.getByLabelText("Filter name"), "mex");
  await user.type(screen.getByLabelText("Filter type_id"), "36");

  const latestCall = mockUseDatabaseTable.mock.calls[mockUseDatabaseTable.mock.calls.length - 1] as [
    string | null,
    DatabaseTableQuery,
  ];
  expect(latestCall[1]).toMatchObject({
    columnFilters: {
      name: "mex",
      type_id: "36",
    },
  });
  expect(screen.getByText("Mexallon")).toBeInTheDocument();
  expect(screen.queryByText("Pyerite")).not.toBeInTheDocument();
});

test("shows a readable error when the table list is unavailable", () => {
  mockTablesState.data = [];
  mockTablesState.error = new Error("Database is busy");
  mockUseDatabaseTable.mockImplementation(() => ({
    isLoading: false,
    error: null,
    data: undefined,
  }));

  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DatabasePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(screen.getByText("Database table list is temporarily unavailable.")).toBeInTheDocument();
  expect(screen.getByText("Could not load database tables right now.")).toBeInTheDocument();
});
