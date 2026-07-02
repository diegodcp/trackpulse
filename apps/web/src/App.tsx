import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppProvider, useAppContext } from './context/AppContext';
import { SessionSelector } from './components/SessionSelector';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
});

function AppContent() {
  const { selectedSessionName, clearSession } = useAppContext();

  return (
    <div className="app">
      <header>
        <h1>TrackPulse</h1>
        {selectedSessionName && (
          <div className="selected-session">
            <span>{selectedSessionName}</span>
            <button onClick={clearSession}>✕</button>
          </div>
        )}
      </header>
      <main>
        {!selectedSessionName ? (
          <SessionSelector />
        ) : (
          <p>Session loaded: {selectedSessionName}</p>
        )}
      </main>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <AppContent />
      </AppProvider>
    </QueryClientProvider>
  );
}
