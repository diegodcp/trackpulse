import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/AppShell';
import { InsightPanel } from './components/InsightPanel';
import { LayerToggleBar } from './components/LayerToggleBar';
import { SessionStatusBar } from './components/SessionStatusBar';
import { TrackMapPanel } from './components/TrackMapPanel';
import { mockInsights } from './data/mockInsights';

const LAYERS = [
  'Track Temp',
  'Grip',
  'Corner Evolution',
  'Wind',
  'Traffic',
  'Dirty',
  'Tyres',
  'Rain',
  'Cars'
];

export function App() {
  const [activeLayer, setActiveLayer] = useState(LAYERS[0]);
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <AppShell statusSlot={<SessionStatusBar />}>
        <TrackMapPanel activeLayer={activeLayer} />
        <LayerToggleBar
          layers={LAYERS}
          activeLayer={activeLayer}
          onLayerChange={setActiveLayer}
        />
        <InsightPanel insights={mockInsights} />
      </AppShell>
    </QueryClientProvider>
  );
}
