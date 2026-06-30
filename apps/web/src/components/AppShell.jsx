export function AppShell({ statusSlot, children }) {
  return (
    <div className="app-shell">
      <div className="top-bar">
        <header className="app-header">
          <p className="app-kicker">Condition Intelligence Layer</p>
          <h1>TrackPulse</h1>
        </header>
        {statusSlot}
      </div>
      <main>{children}</main>
    </div>
  );
}
