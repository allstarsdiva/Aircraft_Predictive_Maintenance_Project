"use client";

import { useCallback, useEffect, useState } from "react";
import { isAbort, postJson, request } from "@/lib/api/client";
import { MODEL_SYSTEMS } from "@/lib/models/catalog";
import type { ModelRun } from "@/lib/models/triage";
import type { DatasetExample, HistoryEntry, PredictionResponse } from "@/lib/models/types";

/** Runs each saved subsystem model on one dataset example (normal or challenge). */
export function useModelRuns(variant: "normal" | "challenge") {
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setRuns([]);
    Promise.all(
      MODEL_SYSTEMS.map(async (system): Promise<ModelRun> => {
        try {
          const example = await request<DatasetExample>(`/api/workspace/examples/${system.key}?variant=${variant}`, { signal: controller.signal });
          const result = await postJson<PredictionResponse>(system.endpoint, example.payload, controller.signal);
          return { system, example, result };
        } catch (error) {
          if (isAbort(error)) throw error;
          return { system, error: (error as Error).message };
        }
      }),
    )
      .then((responses) => {
        if (!controller.signal.aborted) setRuns(responses);
      })
      .catch((error) => {
        if (!isAbort(error)) setRuns(MODEL_SYSTEMS.map((system) => ({ system, error: (error as Error).message })));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [variant, tick]);

  const refresh = useCallback(() => setTick((v) => v + 1), []);
  return { runs, loading, refresh, tick };
}

/** Saved user prediction runs (summaries only, no raw sensor values). */
export function usePredictionHistory(tick: number) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    request<HistoryEntry[]>("/api/prediction-history?limit=100", { signal: controller.signal })
      .then((records) => {
        if (!controller.signal.aborted) setHistory(Array.isArray(records) ? records : []);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setHistory([]);
          setError((err as Error).message || "Could not load saved prediction history.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [tick]);

  return { history, loading, error };
}
