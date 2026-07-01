import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { BahrainCircuitDemo } from './demo/BahrainCircuitDemo';
import './styles.css';

const isBahrainMapDemoRoute = window.location.pathname === '/demo/bahrain-map';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isBahrainMapDemoRoute ? <BahrainCircuitDemo /> : <App />}
  </React.StrictMode>
);
