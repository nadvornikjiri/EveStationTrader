import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/trade", label: "Trade" },
  { to: "/sync", label: "Sync" },
  { to: "/characters", label: "Characters" },
  { to: "/database", label: "Database" },
  { to: "/settings", label: "Settings" },
];

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-kicker">EVE Online</span>
          <h1>EVE Station Trader</h1>
        </div>
        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className="nav-link">
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
