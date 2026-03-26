import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CharactersPage } from "./CharactersPage";

const mockUseCharacters = vi.fn();
const mockConnectMutate = vi.fn();

vi.mock("../hooks/useCharacterData", () => ({
  useCharacters: () => mockUseCharacters(),
  useConnectCharacter: () => ({
    mutate: mockConnectMutate,
    isPending: false,
  }),
}));

const characters = [
  {
    id: 90000001,
    character_name: "Demo Trader",
    corporation_name: "Open Traders Union",
    granted_scopes: ["esi-assets.read_assets.v1", "esi-markets.structure_markets.v1"],
    sync_enabled: true,
    last_token_refresh: "2026-03-26T10:00:00Z",
    last_successful_sync: "2026-03-26T09:00:00Z",
    assets_sync_status: "ok",
    orders_sync_status: "ok",
    skills_sync_status: "pending",
    structures_sync_status: "ok",
    accessible_structure_count: 3,
  },
];

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CharactersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockUseCharacters.mockReturnValue({ data: characters, isLoading: false });
});

afterEach(() => {
  vi.clearAllMocks();
});

test("renders character list with all spec columns", () => {
  renderPage();

  expect(screen.getByText("Connected Pilots")).toBeInTheDocument();
  expect(screen.getByText("1 connected")).toBeInTheDocument();

  const table = screen.getByRole("table");
  const headers = within(table).getAllByRole("columnheader").map((th) => th.textContent);
  for (const col of [
    "Character", "Corporation", "Scopes", "Sync",
    "Last Token Refresh", "Last Sync",
    "Assets", "Orders", "Skills", "Structures",
    "Accessible Structures",
  ]) {
    expect(headers).toContain(col);
  }

  expect(within(table).getByText("Demo Trader")).toBeInTheDocument();
  expect(within(table).getByText("Open Traders Union")).toBeInTheDocument();
  expect(within(table).getByText("Enabled")).toBeInTheDocument();
  expect(within(table).getByText("3")).toBeInTheDocument();
});

test("shows empty state when no characters are connected", () => {
  mockUseCharacters.mockReturnValue({ data: [], isLoading: false });
  renderPage();

  expect(screen.getByText(/No characters connected yet/)).toBeInTheDocument();
});

test("connect button calls mutation", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByText("Connect New Character"));
  expect(mockConnectMutate).toHaveBeenCalled();
});
