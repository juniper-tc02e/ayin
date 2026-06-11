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

export type User = {
  id: string;
  email: string;
  email_verified: boolean;
  created_at: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export type ScanJob = {
  connector_id: string;
  status: "queued" | "running" | "done" | "failed";
  findings_count: number;
  attempts: number;
  error: string | null;
};

export type Scan = {
  id: string;
  status: string;
  error: string | null;
  source_set: string[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: { jobs_total: number; jobs_done: number; jobs_failed: number };
  jobs: ScanJob[];
};

export type Finding = {
  id: string;
  category: "credential" | "broker" | "social" | "records" | "linkage";
  sensitivity: "low" | "medium" | "high" | "critical";
  source: string;
  source_name: string;
  source_url: string | null;
  captured_at: string;
  confidence: number;
  exploitability: number | null;
  summary: string;
  payload: Record<string, unknown>;
  identifier_id: string | null;
  state: string;
  step_up_required: boolean;
  match_status: "auto_matched" | "possible" | "confirmed" | "rejected";
  match_confidence: number | null;
  corroboration_count: number;
  merged_sources: { source: string; source_name: string }[];
  conflicts: { field: string; values: { value: string; source: string }[] }[];
};

export type FindingsPage = {
  scan_id: string;
  findings: Finding[];
  locked_credential_findings: number;
};

export type ScoreContributor = {
  finding_id: string;
  category: string;
  points: number;
  reason: string;
};

export type ScoreData = {
  scan_id: string;
  overall: number;
  subscores: Record<string, number>;
  rubric_version: string;
  computed_at: string;
  verdict: string;
  contributing: ScoreContributor[];
};

/** JSON fetch with session cookie included; throws ApiError on non-2xx. */
export async function api<T>(
  path: string,
  init?: { method?: string; body?: unknown; headers?: Record<string, string> }
): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: init?.method ?? "GET",
    credentials: "include",
    headers: {
      ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail?.reason) detail = data.detail.reason;
      else if (data.detail?.message) detail = data.detail.message;
      else detail = JSON.stringify(data.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export type ChecklistItem = {
  finding_id: string;
  category: string;
  sensitivity: string;
  title: string;
  steps: string[];
  expected_score_delta: number;
  effort: "low" | "medium";
};

export type Checklist = {
  scan_id: string;
  current_overall: number;
  items: ChecklistItem[];
};

export type AccountSummary = {
  email: string;
  identifiers: number;
  scans: number;
  findings: number;
  vault_items: number;
  pii_retention_days: number;
  note: string;
};
