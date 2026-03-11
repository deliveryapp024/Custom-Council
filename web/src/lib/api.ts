export const API_BASE = "http://localhost:8000/api";

export interface Stage1Result {
  member_name: string;
  engine: string;
  model: string;
  ok: boolean;
  response: string;
  error?: string | null;
  duration_ms: number;
}

export interface Stage2Result {
  reviewer_name: string;
  reviewer_engine: string;
  reviewer_model: string;
  ok: boolean;
  ranking_text: string;
  parsed_ranking: string[];
  label_to_member: Record<string, string>;
  duration_ms: number;
  error?: string | null;
}

export interface AggregateRanking {
  member_name: string;
  average_rank: number;
  rankings_count: number;
}

export interface RunDetail {
  id: string;
  task: string;
  project_path: string;
  created_at: string;
  status: "running" | "stage1" | "stage2" | "stage3" | "awaiting_approval" | "approved" | "rejected" | "error" | "editing";
  stage1_results: Stage1Result[];
  stage2_results: Stage2Result[];
  aggregate_rankings: AggregateRanking[];
  chairman_output: string;
  edit_feedback?: string;
  duration_ms: number;
  error: string | null;
}

export interface RunSummary {
  id: string;
  task: string;
  status: string;
  created_at: string;
  duration_ms: number;
  members_ok: number;
  members_total: number;
}

export async function startRun(task: string, projectPath: string): Promise<{ id: string; status: string }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, project_path: projectPath }),
  });
  if (!res.ok) throw new Error("Failed to start run");
  return res.json();
}

export async function listRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_BASE}/runs`);
  if (!res.ok) throw new Error("Failed to fetch runs");
  return res.json();
}

export async function getRun(id: string): Promise<RunDetail> {
  const res = await fetch(`${API_BASE}/runs/${id}`);
  if (!res.ok) throw new Error("Failed to fetch run details");
  return res.json();
}

export async function approveRun(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/runs/${id}/approve`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to approve");
}

export async function rejectRun(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/runs/${id}/reject`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reject");
}

export async function stopRun(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/runs/${id}/stop`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to stop run");
}

export async function editRun(id: string, feedback: string): Promise<void> {
  const res = await fetch(`${API_BASE}/runs/${id}/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
  if (!res.ok) throw new Error("Failed to submit feedback");
}

export async function getConfig(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}
