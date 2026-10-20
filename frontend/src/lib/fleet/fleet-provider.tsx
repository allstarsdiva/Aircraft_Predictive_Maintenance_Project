"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { generateFleet, seededRng, tickFleet } from "./generate.ts";
import type { Aircraft } from "./types.ts";

const INITIAL_SEED = 20261017;
const TICK_MS = 2500;

interface FleetState {
  fleet: Aircraft[];
  connected: boolean;
  lastSync: Date | null;
  toggleConnected: () => void;
  resync: () => void;
}

const FleetContext = createContext<FleetState | null>(null);

/**
 * Holds the simulated fleet for every page of the simulation workspace and
 * runs the simulated telemetry tick while "live" is on.
 */
export function FleetProvider({ children }: { children: ReactNode }) {
  const [fleet, setFleet] = useState<Aircraft[]>(() => generateFleet(seededRng(INITIAL_SEED)));
  const [connected, setConnected] = useState(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);

  useEffect(() => {
    setLastSync(new Date());
  }, []);

  useEffect(() => {
    if (!connected) return;
    const id = window.setInterval(() => {
      setFleet((prev) => tickFleet(prev));
      setLastSync(new Date());
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, [connected]);

  const toggleConnected = useCallback(() => setConnected((v) => !v), []);
  const resync = useCallback(() => {
    setFleet(generateFleet(seededRng(Date.now() >>> 0)));
    setLastSync(new Date());
  }, []);

  const value = useMemo(
    () => ({ fleet, connected, lastSync, toggleConnected, resync }),
    [fleet, connected, lastSync, toggleConnected, resync],
  );
  return <FleetContext.Provider value={value}>{children}</FleetContext.Provider>;
}

export function useFleet(): FleetState {
  const ctx = useContext(FleetContext);
  if (!ctx) throw new Error("useFleet must be used inside <FleetProvider>.");
  return ctx;
}
