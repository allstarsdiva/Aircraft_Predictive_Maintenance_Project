# AeroPredict frontend (Next.js)

A TypeScript dashboard for the aircraft predictive-maintenance backend, built with
Next.js 16 (App Router), React 19, Tailwind CSS v4, shadcn/ui-style components,
Chakra UI (tables, progress) and Framer Motion. It has a light theme and a
true-black dark theme (toggle at the top of the sidebar).

The fleet pages run on a **simulated** fleet (seeded, updated every 2.5 s); they are
not live aircraft data. The Models pages call the real FastAPI models.

## Run

Start the backend first, from the repository root:

    .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

Then, in this folder:

    npm install
    npm run dev          # http://127.0.0.1:3000

| Script | What it does |
|---|---|
| `npm run dev` | Development server on 127.0.0.1:3000 |
| `npm run build` / `npm start` | Production build and server |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Node's built-in test runner on `src/**/*.test.ts` |

## Backend connection

Requests to `/api/*` go through `src/app/api/[...path]/route.ts`, which forwards them
to FastAPI. Configure it with server-side environment variables:

- `AIRCRAFT_API_TARGET` — backend URL (default `http://127.0.0.1:8000`)
- `AIRCRAFT_API_KEY` — sent as `X-API-Key` when set; never exposed to the browser

If the backend is down, the proxy returns HTTP 502 and the Models pages say so.

## Pages

| Route | Page |
|---|---|
| `/` | Fleet overview: ticker, KPIs, fleet-health chart, movers, health heatmap, watchlist |
| `/analytics` | Aircraft health candles, RUL trend, RUL by subsystem, risk mix |
| `/maintenance` | Work queue with priority filter and search |
| `/aircraft/[id]`, `/aircraft/[id]/[component]` | Aircraft and component detail |
| `/models/predict` | Run the trained models (examples, CSV/JSON import, input check, reports) |
| `/models/coverage`, `/models/review` | Model coverage and review of recorded predictions |

## Structure

- `src/app/` — routes (thin server components) and the API proxy
- `src/components/` — `ui/` primitives, `charts/`, `fleet/`, `models/`, `shell/` (sidebar, page parts)
- `src/lib/` — chart palette and helpers (`viz.ts`), simulated fleet (`fleet/`), model helpers (`models/`), API client
