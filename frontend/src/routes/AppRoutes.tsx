import { Route, Routes, Navigate } from "react-router-dom";

import { AppShell } from "../components/common/AppShell";
import { CharacterDetailPage } from "../pages/CharacterDetailPage";
import { CharactersPage } from "../pages/CharactersPage";
import { DatabasePage } from "../pages/DatabasePage";
import { SettingsPage } from "../pages/SettingsPage";
import { SyncPage } from "../pages/SyncPage";
import { TradePage } from "../pages/TradePage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/trade" replace />} />
        <Route path="/trade" element={<TradePage />} />
        <Route path="/sync" element={<SyncPage />} />
        <Route path="/characters" element={<CharactersPage />} />
        <Route path="/characters/:id" element={<CharacterDetailPage />} />
        <Route path="/database" element={<DatabasePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
