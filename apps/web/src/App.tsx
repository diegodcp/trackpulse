import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="app">
        <header>
          <h1>TrackPulse</h1>
        </header>
        <main>
          <p>Select a session to begin</p>
        </main>
      </div>
    </QueryClientProvider>
  );
}
