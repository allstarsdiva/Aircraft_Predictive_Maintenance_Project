import { friendlyApiError } from "@/lib/models/upload-validation";

/**
 * Browser-side JSON client. Every path is same-origin ("/api/..."); the
 * Next.js route handler in src/app/api forwards it to FastAPI and adds the
 * server-side API key, so no secret ever reaches the browser bundle.
 */
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new Error("Cannot reach the frontend server's API proxy. Make sure `npm run dev` is still running.");
  }
  const text = await response.text();
  let body: { detail?: unknown } & Record<string, unknown>;
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error("Backend returned a non-JSON response. Check the API address.");
  }
  if (!response.ok) throw new Error(friendlyApiError(response.status, body?.detail));
  return body as T;
}

export function postJson<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export const isAbort = (err: unknown): boolean => (err as Error)?.name === "AbortError";
