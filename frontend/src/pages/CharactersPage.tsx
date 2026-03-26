import { Link } from "react-router-dom";

import { useCharacters, useConnectCharacter } from "../hooks/useCharacterData";

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
          {connectMutation.isPending ? "Redirecting..." : "Connect New Character"}
        </button>
      </header>
      <section className="panel">
        <div className="panel-header">
          <h2>Character Management</h2>
          <span>{characters.length} connected</span>
        </div>
        {isLoading ? (
          <p>Loading characters...</p>
        ) : characters.length === 0 ? (
          <p>No characters connected yet. Click "Connect New Character" to add one via EVE SSO.</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Character</th>
                  <th>Corporation</th>
                  <th>Scopes</th>
                  <th>Sync</th>
                  <th>Last Token Refresh</th>
                  <th>Last Sync</th>
                  <th>Assets</th>
                  <th>Orders</th>
                  <th>Skills</th>
                  <th>Structures</th>
                  <th>Accessible Structures</th>
                </tr>
              </thead>
              <tbody>
                {characters.map((char) => (
                  <tr key={char.id}>
                    <td>
                      <Link to={`/characters/${char.id}`}>{char.character_name}</Link>
                    </td>
                    <td>{char.corporation_name ?? "\u2014"}</td>
                    <td>{char.granted_scopes.length}</td>
                    <td>{char.sync_enabled ? "Enabled" : "Disabled"}</td>
                    <td>{char.last_token_refresh ? new Date(char.last_token_refresh).toLocaleString() : "\u2014"}</td>
                    <td>{char.last_successful_sync ? new Date(char.last_successful_sync).toLocaleString() : "\u2014"}</td>
                    <td>{char.assets_sync_status}</td>
                    <td>{char.orders_sync_status}</td>
                    <td>{char.skills_sync_status}</td>
                    <td>{char.structures_sync_status}</td>
                    <td>{char.accessible_structure_count}</td>
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
