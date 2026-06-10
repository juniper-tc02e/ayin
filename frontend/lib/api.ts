/**
 * API base resolution.
 * - In the browser: NEXT_PUBLIC_API_URL (http://localhost:8000 in dev).
 * - In server components inside docker compose: API_INTERNAL_URL (http://api:8000).
 */
export function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export type Health = {
  status: "ok" | "degraded";
  db: "ok" | "down";
  redis: "ok" | "down";
  version: string;
};

export async function fetchHealth(): Promise<Health | null> {
  try {
    const res = await fetch(`${apiBase()}/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}
