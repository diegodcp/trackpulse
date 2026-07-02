import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppProvider, useAppContext } from './context/AppContext';
import { SessionSelector } from './components/SessionSelector';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
});

function AppContent() {
  const { selectedSessionName, clearSession } = useAppContext();

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__logo">
          <span className="app__logo-accent">Track</span>Pulse
        </h1>
        {selectedSessionName && (
          <div className="app__selected-session">
            <span>{selectedSessionName}</span>
            <button className="app__clear-btn" onClick={clearSession}>✕</button>
          </div>
        )}
      </header>
      <main className="app__main">
        {!selectedSessionName ? (
          <SessionSelector />
        ) : (
          <p className="app__placeholder">Session loaded: {selectedSessionName}</p>
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
