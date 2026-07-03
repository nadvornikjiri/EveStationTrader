import { Link } from "react-router-dom";

import { useCharacters, useConnectCharacter } from "../hooks/useCharacterData";

function SyncBadge({ status }: { status: string }) {
  const color =
    status === "ok"
      ? "var(--metric-positive)"
      : status === "pending"
        ? "var(--metric-capital)"
        : "var(--metric-negative, #f44)";
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        backgroundColor: color,
        marginRight: 4,
        verticalAlign: "middle",
      }}
      title={status}
    />
  );
}

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " " +
    d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function CharactersPage() {
  const { data: characters = [], isLoading } = useCharacters();
  const connectMutation = useConnectCharacter();

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Characters</span>
          <h1>Connected Pilots</h1>
        </div>
        <button
          className="refresh-button"
          onClick={() => connectMutation.mutate()}
          disabled={connectMutation.isPending}
        >
          {connectMutation.isPending ? "Redirecting..." : "Connect or Reconnect Character"}
        </button>
      </header>
      <section className="panel">
        <div className="panel-header">
          <h2>Character Management</h2>
          <span>{characters.length} connected</span>
        </div>
        <p>
          New connections request the scopes needed for asset visibility, character sell orders, skills, and structure
          access.
        </p>
        {isLoading ? (
          <p>Loading characters...</p>
        ) : characters.length === 0 ? (
          <p>No characters connected yet. Click "Connect or Reconnect Character" to add one via EVE SSO.</p>
        ) : (
          <div className="characters-card-list">
            {characters.map((char) => (
              <div key={char.id} className="character-card panel">
                <div className="character-card-header">
                  <Link to={`/characters/${char.id}`} className="character-card-name">
                    {char.character_name}
                  </Link>
                  <span className="character-card-corp">{char.corporation_name ?? "\u2014"}</span>
                </div>

                <div className="character-card-grid">
                  <div className="character-card-field">
                    <span className="character-card-label">Sync</span>
                    <span>{char.sync_enabled ? "Enabled" : "Disabled"}</span>
                  </div>
                  <div className="character-card-field">
                    <span className="character-card-label">Last Sync</span>
                    <span>{formatTimestamp(char.last_successful_sync)}</span>
                  </div>
                  <div className="character-card-field">
                    <span className="character-card-label">Token Refresh</span>
                    <span>{formatTimestamp(char.last_token_refresh)}</span>
                  </div>
                  <div className="character-card-field">
                    <span className="character-card-label">Structures</span>
                    <span>{char.accessible_structure_count}</span>
                  </div>
                </div>

                <div className="character-card-sync-row">
                  <span><SyncBadge status={char.assets_sync_status} />Assets</span>
                  <span><SyncBadge status={char.orders_sync_status} />Orders</span>
                  <span><SyncBadge status={char.skills_sync_status} />Skills</span>
                  <span><SyncBadge status={char.structures_sync_status} />Structures</span>
                </div>

                <details className="character-card-scopes">
                  <summary>{char.granted_scopes.length} scopes granted</summary>
                  <ul>
                    {char.granted_scopes.map((scope) => (
                      <li key={scope}>{scope}</li>
                    ))}
                  </ul>
                </details>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
