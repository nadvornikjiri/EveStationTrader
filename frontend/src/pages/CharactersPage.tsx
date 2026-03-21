export function CharactersPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Characters</span>
          <h1>Connected Pilots</h1>
        </div>
      </header>
      <section className="panel">
        <div className="panel-header">
          <h2>Character Management</h2>
          <button className="refresh-button">Connect New Character</button>
        </div>
        <p>Character sync state, granted scopes, and discovered structures will render here.</p>
      </section>
    </div>
  );
}
