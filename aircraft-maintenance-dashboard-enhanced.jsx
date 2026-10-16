import React, { lazy, Suspense, useState } from 'react';
import { BrainCircuit, ClipboardList, LayoutGrid, Plane } from 'lucide-react';

const ModelOperationsView = lazy(() => import('./frontend-src/ModelOperations.jsx'));
const ModelWorkspace = lazy(() => import('./frontend-src/ModelWorkspace.jsx'));

const NAV_ITEMS = [
  { key: 'models', label: 'AI Predictions', icon: BrainCircuit },
  { key: 'fleet', label: 'Fleet', icon: LayoutGrid },
  { key: 'maintenance', label: 'Maintenance', icon: ClipboardList },
];

export function AircraftMaintenanceDashboard() {
  const [view, setView] = useState('models');
  const showingModelResults = view === 'fleet' || view === 'maintenance';

  return <div className="min-h-screen bg-slate-950 font-sans text-slate-200">
    <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-400/10 ring-1 ring-cyan-400/30"><Plane className="h-4 w-4 text-cyan-400" /></div>
          <div><div className="text-sm font-bold leading-tight text-slate-100">AeroPredict</div><div className="text-[10px] leading-tight text-slate-500">Predictive Maintenance Console</div></div>
        </div>
        <nav aria-label="Main dashboard" className="hidden items-center gap-1 sm:flex">
          {NAV_ITEMS.map(({ key, label, icon: Icon }) => <button key={key} type="button" onClick={() => setView(key)} aria-current={view === key ? 'page' : undefined}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${view === key ? 'bg-slate-800 text-slate-100' : 'text-slate-500 hover:text-slate-300'}`}>
            <Icon className="h-3.5 w-3.5" /> {label}
          </button>)}
        </nav>
        <div className="text-right text-[10px] text-slate-500">{view === 'fleet' ? 'Fleet health snapshot' : view === 'maintenance' ? 'Component attention review' : 'Research model workspace'}</div>
      </div>
      <nav aria-label="Main dashboard" className="flex border-t border-slate-800 sm:hidden">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => <button key={key} type="button" onClick={() => setView(key)} aria-current={view === key ? 'page' : undefined}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-xs font-semibold ${view === key ? 'text-cyan-400' : 'text-slate-500'}`}>
          <Icon className="h-3.5 w-3.5" /> {label}
        </button>)}
      </nav>
    </header>

    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <Suspense fallback={<div role="status" aria-live="polite" className="mx-auto max-w-7xl py-12 text-center text-sm text-slate-400">Loading {view === 'models' ? 'AI Predictions' : view === 'fleet' ? 'Fleet' : 'Maintenance'}…</div>}>
        {view === 'models' && <ModelWorkspace />}
        {showingModelResults && <ModelOperationsView mode={view} />}
      </Suspense>
    </main>

    <footer className="mx-auto max-w-7xl px-4 pb-6 text-center text-[11px] text-slate-600 sm:px-6">
      {view === 'models' ? 'AeroPredict AI predictions - results are returned by the FastAPI backend' : 'AeroPredict research outputs - no live aircraft telemetry or maintenance records are connected'}
    </footer>
  </div>;
}

export default AircraftMaintenanceDashboard;
