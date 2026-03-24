import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { DatabasePage } from "./DatabasePage";

const mockTablesState = vi.hoisted(() => ({
  data: [
    { name: "items", row_count: 2 },
    { name: "locations", row_count: 3 },
  ],
  error: null as Error | null,
}));

const mockTableState = vi.hoisted(() => ({
  isLoading: false,
  error: null as Error | null,
  data: {
    table_name: "items",
    columns: ["id", "type_id", "name"],
    rows: [
      { id: 1, type_id: 34, name: "Tritanium" },
      { id: 2, type_id: 35, name: "Pyerite" },
    ],
    row_count: 2,
    limit: 200,
  },
}));

vi.mock("../hooks/useDatabaseData", () => ({
  useDatabaseTables: () => mockTablesState,
  useDatabaseTable: () => mockTableState,
}));

afterEach(() => {
  mockTablesState.data = [
    { name: "items", row_count: 2 },
    { name: "locations", row_count: 3 },
  ];
  mockTablesState.error = null;
  mockTableState.isLoading = false;
  mockTableState.error = null;
  mockTableState.data = {
    table_name: "items",
    columns: ["id", "type_id", "name"],
    rows: [
      { id: 1, type_id: 34, name: "Tritanium" },
      { id: 2, type_id: 35, name: "Pyerite" },
    ],
    row_count: 2,
    limit: 200,
  };
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
  expect(screen.getByText("Tritanium")).toBeInTheDocument();
  expect(screen.getByText("Pyerite")).toBeInTheDocument();
});

test("shows a readable error when the table list is unavailable", () => {
  mockTablesState.data = [];
  mockTablesState.error = new Error("Database is busy");

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
