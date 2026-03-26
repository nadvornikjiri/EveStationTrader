import { useParams, Link } from "react-router-dom";

import {
  useCharacterDetail,
  usePatchCharacter,
  useSyncCharacter,
  useTrackStructure,
} from "../hooks/useCharacterData";

export function CharacterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const characterId = id ? Number.parseInt(id, 10) : null;
  const { data: detail, isLoading } = useCharacterDetail(characterId);
  const syncMutation = useSyncCharacter();
  const patchMutation = usePatchCharacter();
  const trackMutation = useTrackStructure();

  if (isLoading || !detail) {
    return (
      <div className="page-stack">
        <header className="page-header">
          <div>
            <span className="eyebrow">Character Detail</span>
            <h1>{isLoading ? "Loading..." : "Character Not Found"}</h1>
          </div>
        </header>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">
            <Link to="/characters">Characters</Link> / Detail
          </span>
          <h1>{detail.character_name}</h1>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className="refresh-button"
            onClick={() => syncMutation.mutate(detail.id)}
            disabled={syncMutation.isPending}
          >
            {syncMutation.isPending ? "Syncing..." : "Sync Now"}
          </button>
          <button
            className="refresh-button"
            onClick={() =>
              patchMutation.mutate({ characterId: detail.id, syncEnabled: !detail.sync_enabled })
            }
            disabled={patchMutation.isPending}
          >
            {detail.sync_enabled ? "Disable Sync" : "Enable Sync"}
          </button>
        </div>
      </header>

      <section className="panel">
        <div className="panel-header">
          <h2>Identity</h2>
        </div>
        <dl className="detail-grid">
          <dt>Corporation</dt>
          <dd>{detail.corporation_name ?? "\u2014"}</dd>
          <dt>Sync Enabled</dt>
          <dd>{detail.sync_enabled ? "Yes" : "No"}</dd>
          <dt>Granted Scopes</dt>
          <dd>{detail.granted_scopes.length > 0 ? detail.granted_scopes.join(", ") : "None"}</dd>
        </dl>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Sync Toggles</h2>
        </div>
        {Object.keys(detail.sync_toggles).length === 0 ? (
          <p>No sync toggles configured.</p>
        ) : (
          <dl className="detail-grid">
            {Object.entries(detail.sync_toggles).map(([domain, enabled]) => (
              <div key={domain}>
                <dt>{domain}</dt>
                <dd>{enabled ? "Enabled" : "Disabled"}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Accessible Structures</h2>
          <span>{detail.structures.length} structures</span>
        </div>
        {detail.structures.length === 0 ? (
          <p>No accessible structures discovered yet. Run a sync to discover structures.</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Structure</th>
                  <th>Structure ID</th>
                  <th>System</th>
                  <th>Region</th>
                  <th>Access Verified</th>
                  <th>Tracking</th>
                  <th>Polling Tier</th>
                  <th>Last Snapshot</th>
                  <th>Confidence</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {detail.structures.map((s) => (
                  <tr key={s.structure_id}>
                    <td>{s.structure_name}</td>
                    <td>{s.structure_id}</td>
                    <td>{s.system_name ?? "\u2014"}</td>
                    <td>{s.region_name ?? "\u2014"}</td>
                    <td>{new Date(s.access_verified_at).toLocaleString()}</td>
                    <td>{s.tracking_enabled ? "Yes" : "No"}</td>
                    <td>{s.polling_tier}</td>
                    <td>{s.last_snapshot_at ? new Date(s.last_snapshot_at).toLocaleString() : "\u2014"}</td>
                    <td>{(s.confidence_score * 100).toFixed(0)}%</td>
                    <td>
                      {!s.tracking_enabled && (
                        <button
                          className="refresh-button"
                          onClick={() =>
                            trackMutation.mutate({ characterId: detail.id, structureId: s.structure_id })
                          }
                          disabled={trackMutation.isPending}
                        >
                          Track
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {detail.skills.length > 0 && (
        <section className="panel">
          <div className="panel-header">
            <h2>Skills</h2>
            <span>{detail.skills.length} skills</span>
          </div>
          <p>{detail.skills.join(", ")}</p>
        </section>
      )}
    </div>
  );
}
