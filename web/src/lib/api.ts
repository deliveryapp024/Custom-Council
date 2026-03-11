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

export interface ApprovalRecord {
  id: string;
  gate: "plan" | "execution" | "completion";
  decision: "approved" | "rejected" | "edited";
  run_id: string;
  task_id?: string | null;
  attempt_id?: string | null;
  actor: string;
  notes: string;
  created_at: string;
}

export interface TaskAssignment {
  id: string;
  task_id: string;
  run_id: string;
  agent_id: string;
  selected_skills: string[];
  assigned_by: string;
  assigned_at: string;
  approval_state: "pending" | "approved" | "rejected";
  notes: string;
}

export interface ExecutionAttempt {
  id: string;
  task_id: string;
  run_id: string;
  attempt_no: number;
  agent_id: string;
  prompt: string;
  started_at: string;
  finished_at?: string | null;
  exit_code?: number | null;
  stdout: string;
  stderr: string;
  test_result: string;
  logs_path?: string | null;
}

export interface QAFinding {
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  details: string;
  suggested_fix: string;
}

export interface QAReport {
  id: string;
  task_id: string;
  run_id: string;
  attempt_id?: string | null;
  agent_id: string;
  summary: string;
  findings: QAFinding[];
  recommendation: "pass" | "fail";
  raw_output: string;
  created_at: string;
}

export interface TaskRecord {
  id: string;
  run_id: string;
  title: string;
  description: string;
  status:
    | "awaiting_assignment"
    | "awaiting_execution_approval"
    | "executing"
    | "qa_review"
    | "execution_retry_needed"
    | "awaiting_completion_approval"
    | "completed"
    | "rejected"
    | "failed";
  priority: number;
  depends_on: string[];
  recommended_agent_id?: string | null;
  recommended_skills: string[];
  selected_agent_id?: string | null;
  selected_skills: string[];
  routing_reason?: string | null;
  created_at: string;
  updated_at: string;
  latest_attempt_id?: string | null;
  latest_qa_report_id?: string | null;
  worktree_path?: string | null;
  branch_name?: string | null;
  assignments: TaskAssignment[];
  attempts: ExecutionAttempt[];
  qa_reports: QAReport[];
  approvals: ApprovalRecord[];
}

export interface RunDetail {
  id: string;
  task: string;
  project_path: string;
  created_at: string;
  status:
    | "created"
    | "stage1"
    | "stage2"
    | "stage3"
    | "awaiting_plan_approval"
    | "plan_approved"
    | "task_graph_ready"
    | "awaiting_execution_approval"
    | "executing"
    | "awaiting_commit_approval"
    | "qa_review"
    | "awaiting_completion_approval"
    | "completed"
    | "rejected"
    | "failed";
  stage1_results: Stage1Result[];
  stage2_results: Stage2Result[];
  aggregate_rankings: AggregateRanking[];
  chairman_output: string;
  duration_ms: number;
  error: string | null;
  workspace_path?: string | null;
  branch_name?: string | null;
  task_ids: string[];
  tasks: TaskRecord[];
  approvals: ApprovalRecord[];
  assignments: TaskAssignment[];
}

export interface RunSummary {
  id: string;
  task: string;
  status: string;
  created_at: string;
  duration_ms: number;
  members_ok: number;
  members_total: number;
  task_count: number;
  completed_tasks: number;
}

export interface AgentProfile {
  id: string;
  display_name: string;
  executor_type: "opencode" | "aider" | "kilocode";
  model_override: string;
  enabled_skills: string[];
  allowed_workflows: string[];
  qa_capable: boolean;
}

export interface SkillDefinition {
  id: string;
  name: string;
  description: string;
  tags: string[];
  prompt_preamble: string;
  allowed_agents: string[];
  instructions: string;
  source: string;
  source_path: string;
  mcp_actions?: {
    type: "tool" | "resource" | "prompt";
    server_id: string;
    name: string;
    description: string;
    mutating: boolean;
  }[];
}

export interface MCPServerConfig {
  id: string;
  display_name: string;
  transport: "stdio" | "http";
  command: string;
  args: string[];
  env: Record<string, string>;
  url: string;
  headers: Record<string, string>;
  enabled: boolean;
  project_ids: string[];
  requires_approval_for_tools: string[];
  required_env: string[];
  notes: string;
  missing_env: string[];
  ready: boolean;
}

export interface ProjectProfile {
  id: string;
  name: string;
  root_paths: string[];
  enabled_mcp_servers: string[];
  default_skill_ids: string[];
}

export interface MCPProjectResolution {
  project_profile: ProjectProfile | null;
  servers: MCPServerConfig[];
}

export interface MCPApprovalRecord {
  id: string;
  project_path: string;
  server_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "executed" | "failed";
  actor: string;
  notes: string;
  result_summary: string;
  created_at: string;
  decided_at?: string | null;
  executed_at?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail =
      typeof payload.detail === "string"
        ? payload.detail
        : payload.detail?.message || JSON.stringify(payload.detail || {});
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

export async function startRun(task: string, projectPath: string): Promise<{ id: string; status: string }> {
  return request("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, project_path: projectPath }),
  });
}

export async function listRuns(): Promise<RunSummary[]> {
  return request("/runs");
}

export async function getRun(id: string): Promise<RunDetail> {
  return request(`/runs/${id}`);
}

export async function approvePlan(id: string, notes = ""): Promise<RunDetail> {
  return request(`/runs/${id}/approve-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function rejectPlan(id: string, notes = ""): Promise<RunDetail> {
  return request(`/runs/${id}/reject-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function stopRun(id: string): Promise<{ status: string; message: string }> {
  return request(`/runs/${id}/stop`, { method: "POST" });
}

export async function editRun(id: string, feedback: string): Promise<RunDetail> {
  return request(`/runs/${id}/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export async function getTask(taskId: string): Promise<TaskRecord> {
  return request(`/tasks/${taskId}`);
}

export async function listRunTasks(runId: string): Promise<TaskRecord[]> {
  return request(`/runs/${runId}/tasks`);
}

export async function assignTask(
  taskId: string,
  agentId: string,
  selectedSkills: string[],
  notes = "",
): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, selected_skills: selectedSkills, notes }),
  });
}

export async function approveExecution(taskId: string, notes = ""): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/approve-execution`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function rejectExecution(taskId: string, notes = ""): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/reject-execution`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function executeTask(taskId: string): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/execute`, { method: "POST" });
}

export async function runTaskQa(taskId: string): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/qa`, { method: "POST" });
}

export async function approveCompletion(taskId: string, notes = ""): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/approve-completion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function rejectCompletion(taskId: string, notes = ""): Promise<{ task: TaskRecord; run_status: string }> {
  return request(`/tasks/${taskId}/reject-completion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function listAgents(): Promise<AgentProfile[]> {
  return request("/agents");
}

export async function listSkills(): Promise<SkillDefinition[]> {
  return request("/skills");
}

export async function getConfig(): Promise<unknown> {
  return request("/config");
}

export async function reloadConfig(): Promise<{ status: string; skills: number; mcp_servers: number; project_profiles: number }> {
  return request("/config/reload", { method: "POST" });
}

export async function setMcpServerEnabled(
  serverId: string,
  enabled: boolean,
): Promise<{ status: string; server: MCPServerConfig | null }> {
  return request(`/mcp/servers/${serverId}/enabled`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function resolveMcpProject(projectPath: string): Promise<MCPProjectResolution> {
  return request("/mcp/projects/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_path: projectPath }),
  });
}

export async function listMcpTools(projectPath: string, serverId: string): Promise<unknown> {
  return request(`/mcp/servers/${serverId}/tools`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_path: projectPath }),
  });
}

export async function listMcpResources(projectPath: string, serverId: string): Promise<unknown> {
  return request(`/mcp/servers/${serverId}/resources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_path: projectPath }),
  });
}

export async function listMcpPrompts(projectPath: string, serverId: string): Promise<unknown> {
  return request(`/mcp/servers/${serverId}/prompts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_path: projectPath }),
  });
}

export async function listMcpApprovals(projectPath?: string): Promise<MCPApprovalRecord[]> {
  const suffix = projectPath ? `?project_path=${encodeURIComponent(projectPath)}` : "";
  return request(`/mcp/approvals${suffix}`);
}

export async function createMcpApproval(
  projectPath: string,
  serverId: string,
  toolName: string,
  argumentsPayload: Record<string, unknown>,
  notes = "",
): Promise<MCPApprovalRecord> {
  return request("/mcp/approvals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_path: projectPath,
      server_id: serverId,
      tool_name: toolName,
      arguments: argumentsPayload,
      notes,
    }),
  });
}

export async function approveMcpApproval(id: string, notes = ""): Promise<MCPApprovalRecord> {
  return request(`/mcp/approvals/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function rejectMcpApproval(id: string, notes = ""): Promise<MCPApprovalRecord> {
  return request(`/mcp/approvals/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function executeMcpApproval(id: string): Promise<{ approval: MCPApprovalRecord; result: unknown }> {
  return request(`/mcp/approvals/${id}/execute`, {
    method: "POST",
  });
}
