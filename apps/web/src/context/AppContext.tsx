import { createContext, useContext, useState, ReactNode } from 'react';

interface AppState {
  selectedSessionKey: number | null;
  selectedSessionName: string | null;
  selectSession: (key: number, name: string) => void;
  clearSession: () => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [selectedSessionKey, setKey] = useState<number | null>(null);
  const [selectedSessionName, setName] = useState<string | null>(null);

  return (
    <AppContext.Provider
      value={{
        selectedSessionKey,
        selectedSessionName,
        selectSession: (key, name) => {
          setKey(key);
          setName(name);
        },
        clearSession: () => {
          setKey(null);
          setName(null);
        },
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used within AppProvider');
  return ctx;
}
