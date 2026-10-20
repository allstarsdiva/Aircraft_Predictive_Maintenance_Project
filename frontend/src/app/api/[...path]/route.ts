import { NextResponse, type NextRequest } from "next/server";

/**
 * Same-origin proxy to the FastAPI backend.
 *
 * The browser calls /api/...; this handler forwards to
 * AIRCRAFT_API_TARGET (default http://127.0.0.1:8000) and attaches
 * AIRCRAFT_API_KEY server-side when configured, so the key never enters the
 * client bundle.
 */
export const dynamic = "force-dynamic";

const TARGET = (process.env.AIRCRAFT_API_TARGET || "http://127.0.0.1:8000").replace(/\/$/, "");

type Context = { params: Promise<{ path: string[] }> };

async function proxy(req: NextRequest, { params }: Context) {
  const { path } = await params;
  const url = new URL(req.url);
  const target = `${TARGET}/api/${path.map(encodeURIComponent).join("/")}${url.search}`;

  const headers = new Headers({ accept: req.headers.get("accept") ?? "application/json" });
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const key = process.env.AIRCRAFT_API_KEY?.trim();
  if (key) headers.set("X-API-Key", key);

  const hasBody = !["GET", "HEAD"].includes(req.method);
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
      signal: req.signal,
    });
    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the FastAPI backend at ${TARGET}. Start it with uvicorn on port 8000.` },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
