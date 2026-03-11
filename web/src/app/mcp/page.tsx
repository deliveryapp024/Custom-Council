"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  Loader2,
  RefreshCcw,
  Rocket,
  Server,
  ShieldAlert,
  X,
} from "lucide-react";

import {
  MCPApprovalRecord,
  MCPProjectResolution,
  approveMcpApproval,
  createMcpApproval,
  executeMcpApproval,
  listMcpApprovals,
  listMcpPrompts,
  listMcpResources,
  listMcpTools,
  reloadConfig,
  rejectMcpApproval,
  resolveMcpProject,
  setMcpServerEnabled,
} from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

type CapabilityKind = "tools" | "resources" | "prompts";

function sanitizeCapabilityValue(value: unknown, depth = 0): unknown {
  if (depth > 4) {
    return "[truncated]";
  }
  if (Array.isArray(value)) {
    return value.slice(0, 8).map((item) => sanitizeCapabilityValue(item, depth + 1));
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const next: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(record)) {
      if (key === "icons" && Array.isArray(item)) {
        next[key] = `[${item.length} icon entries hidden]`;
        continue;
      }
      if (key === "src" && typeof item === "string" && item.startsWith("data:")) {
        next[key] = "[data URI hidden]";
        continue;
      }
      next[key] = sanitizeCapabilityValue(item, depth + 1);
    }
    return next;
  }
  if (typeof value === "string") {
    if (value.startsWith("data:")) {
      return "[data URI hidden]";
    }
    if (value.length > 220) {
      return `${value.slice(0, 220)}...`;
    }
  }
  return value;
}

function extractCapabilityItems(kind: CapabilityKind, payload: unknown): { error?: string; items: Record<string, unknown>[] } {
  if (!payload) {
    return { items: [] };
  }
  if (typeof payload === "object" && payload !== null) {
    const record = payload as Record<string, unknown>;
    if (typeof record.error === "string") {
      return { error: record.error, items: [] };
    }
    const list = record[kind];
    if (Array.isArray(list)) {
      return {
        items: list.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null),
      };
    }
  }
  return { items: [] };
}

function getCapabilityTitle(kind: CapabilityKind, item: Record<string, unknown>, index: number): string {
  if (typeof item.name === "string" && item.name) {
    return item.name;
  }
  if (typeof item.uri === "string" && item.uri) {
    return item.uri;
  }
  if (typeof item.title === "string" && item.title) {
    return item.title;
  }
  return `${kind.slice(0, 1).toUpperCase()}${kind.slice(1, -1)} ${index + 1}`;
}

function getCapabilityDescription(item: Record<string, unknown>): string {
  if (typeof item.description === "string" && item.description) {
    return item.description;
  }
  const annotations = item.annotations;
  if (annotations && typeof annotations === "object") {
    const record = annotations as Record<string, unknown>;
    if (typeof record.description === "string" && record.description) {
      return record.description;
    }
    if (typeof record.title === "string" && record.title) {
      return record.title;
    }
  }
  return "No description provided.";
}

function CapabilityPanel({ kind, payload }: { kind: CapabilityKind; payload: unknown }) {
  const { error, items } = extractCapabilityItems(kind, payload);

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
        {error}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 text-sm text-slate-500">
        No {kind} returned.
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[34rem] overflow-y-auto pr-2 custom-scrollbar">
      {items.map((item, index) => {
        const title = getCapabilityTitle(kind, item, index);
        const description = getCapabilityDescription(item);
        const sanitized = sanitizeCapabilityValue(item);
        return (
          <details key={`${kind}-${title}-${index}`} className="group relative rounded-xl border border-slate-800 bg-slate-950/40 open:border-slate-700 open:bg-slate-900/60 transition-colors">
            <summary className="list-none cursor-pointer p-4 pb-3">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="font-medium text-sm text-slate-100 truncate pr-2" title={title}>{title}</div>
                  <div className="text-xs text-slate-400 line-clamp-2 pr-2" title={description}>{description}</div>
                </div>
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-800/50 group-hover:bg-slate-800 transition-colors">
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 transition-transform group-open:rotate-180" />
                </div>
              </div>
            </summary>
            <div className="border-t border-slate-800/80 p-3 pt-2">
              <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs leading-5 text-slate-300 custom-scrollbar">
                {JSON.stringify(sanitized, null, 2)}
              </pre>
            </div>
          </details>
        );
      })}
    </div>
  );
}

function ServerSetupHint({ serverId }: { serverId: string }) {
  if (serverId === "supabase-remote") {
    return (
      <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-sm text-cyan-100">
        <div className="font-medium text-cyan-50">Supabase Remote Setup</div>
        <div className="mt-2 space-y-1 text-cyan-100/90">
          <div>1. Create a Supabase personal access token in your Supabase dashboard.</div>
          <div>2. Put it in <code>council-orchestrator/.env</code> as <code>SUPABASE_ACCESS_TOKEN=...</code>.</div>
          <div>3. Keep <code>SUPABASE_PROJECT_REF</code> set so the hosted MCP server stays scoped to one project.</div>
          <div>4. Click <span className="font-medium">Reload Config</span>, then <span className="font-medium">Inspect</span>.</div>
        </div>
      </div>
    );
  }

  if (serverId === "supabase-local") {
    return (
      <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-sm text-cyan-100">
        <div className="font-medium text-cyan-50">Supabase Local Setup</div>
        <div className="mt-2 space-y-1 text-cyan-100/90">
          <div>1. Install Docker Desktop.</div>
          <div>2. Run <code>supabase start</code> in the linked Supabase project.</div>
          <div>3. Confirm <code>http://127.0.0.1:54321/mcp</code> is reachable, then inspect again.</div>
        </div>
      </div>
    );
  }

  return null;
}

function ServerReadinessAlert({
  enabled,
  ready,
  missingEnv,
}: {
  enabled: boolean;
  ready: boolean;
  missingEnv: string[];
}) {
  if (!enabled) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-200">
        Disabled. Enable the server first, then reload config.
      </div>
    );
  }

  if (!ready && missingEnv.length > 0) {
    return (
      <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
        Missing required credentials: {missingEnv.join(", ")}. Add them to <code>.env</code>, then click <span className="font-medium">Reload Config</span>.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
      Server is ready for inspection.
    </div>
  );
}

export default function McpPage() {
  const [projectPath, setProjectPath] = useState("C:\\Users\\arali\\OneDrive\\Documents\\Playground\\council-orchestrator");
  const [resolution, setResolution] = useState<MCPProjectResolution | null>(null);
  const [approvals, setApprovals] = useState<MCPApprovalRecord[]>([]);
  const [selectedServerId, setSelectedServerId] = useState("");
  const [toolName, setToolName] = useState("");
  const [toolArgs, setToolArgs] = useState("{}");
  const [serverPayloads, setServerPayloads] = useState<Record<string, { tools?: unknown; resources?: unknown; prompts?: unknown }>>({});
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedServer = useMemo(
    () => resolution?.servers.find((server) => server.id === selectedServerId) ?? null,
    [resolution, selectedServerId],
  );
  const enabledServers = useMemo(
    () => resolution?.servers.filter((server) => server.enabled) ?? [],
    [resolution],
  );

  async function refreshAll() {
    setWorking("refresh");
    setError(null);
    try {
      const [resolved, nextApprovals] = await Promise.all([
        resolveMcpProject(projectPath),
        listMcpApprovals(projectPath),
      ]);
      setResolution(resolved);
      setApprovals(nextApprovals);
      if (!selectedServerId && resolved.servers.length > 0) {
        const preferred = resolved.servers.find((server) => server.enabled) ?? resolved.servers[0];
        setSelectedServerId(preferred.id);
      }
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Failed to load MCP data");
    } finally {
      setWorking(null);
    }
  }

  useEffect(() => {
    refreshAll();
  }, []);

  async function loadServerDetails(serverId: string) {
    setWorking(`server-${serverId}`);
    try {
      const [tools, resources, prompts] = await Promise.all([
        listMcpTools(projectPath, serverId).catch((err) => ({ error: err instanceof Error ? err.message : String(err) })),
        listMcpResources(projectPath, serverId).catch((err) => ({ error: err instanceof Error ? err.message : String(err) })),
        listMcpPrompts(projectPath, serverId).catch((err) => ({ error: err instanceof Error ? err.message : String(err) })),
      ]);
      setServerPayloads((current) => ({
        ...current,
        [serverId]: { tools, resources, prompts },
      }));
    } finally {
      setWorking(null);
    }
  }

  async function handleCreateApproval() {
    setWorking("create-approval");
    setError(null);
    try {
      const parsedArgs = JSON.parse(toolArgs) as Record<string, unknown>;
      const record = await createMcpApproval(projectPath, selectedServerId, toolName, parsedArgs);
      setApprovals((current) => [record, ...current]);
      setToolName("");
      setToolArgs("{}");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create approval");
    } finally {
      setWorking(null);
    }
  }

  async function runApprovalAction(
    action: "approve" | "reject" | "execute",
    approvalId: string,
  ) {
    setWorking(`${action}-${approvalId}`);
    setError(null);
    try {
      if (action === "approve") {
        await approveMcpApproval(approvalId);
      } else if (action === "reject") {
        await rejectMcpApproval(approvalId);
      } else {
        await executeMcpApproval(approvalId);
      }
      setApprovals(await listMcpApprovals(projectPath));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : `Failed to ${action} approval`);
    } finally {
      setWorking(null);
    }
  }

  async function handleReloadConfig() {
    setWorking("reload-config");
    setError(null);
    try {
      await reloadConfig();
      await refreshAll();
    } catch (reloadError) {
      setError(reloadError instanceof Error ? reloadError.message : "Failed to reload config");
    } finally {
      setWorking(null);
    }
  }

  async function handleToggleServer(serverId: string, enabled: boolean) {
    setWorking(`toggle-${serverId}`);
    setError(null);
    try {
      await setMcpServerEnabled(serverId, enabled);
      await refreshAll();
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : "Failed to update server state");
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-white">MCP Admin</h1>
        <p className="text-slate-400">
          Resolve project-scoped MCP servers, inspect available capabilities, and use stored human approvals for mutating tool calls.
        </p>
      </div>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto_auto]">
          <input
            value={projectPath}
            onChange={(event) => setProjectPath(event.target.value)}
            className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            placeholder="Project path"
          />
          <button
            onClick={refreshAll}
            disabled={working !== null}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
          >
            {working === "refresh" ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCcw className="w-4 h-4" />}
            Resolve
          </button>
          <button
            onClick={handleReloadConfig}
            disabled={working !== null}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm font-medium text-slate-200 disabled:opacity-50"
          >
            <Rocket className="w-4 h-4" />
            Reload Config
          </button>
        </div>
        {error && <div className="text-sm text-red-300">{error}</div>}
        {resolution?.project_profile && (
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-sm text-cyan-100">
            Profile: <span className="font-medium">{resolution.project_profile.name}</span> ({resolution.project_profile.id})
          </div>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Project Servers</h2>
            {!resolution || resolution.servers.length === 0 ? (
              <div className="text-sm text-slate-500">No MCP servers are enabled for this project profile yet.</div>
            ) : (
              resolution.servers.map((server) => (
                <div key={server.id} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Server className="w-4 h-4 text-cyan-300" />
                        <span className="font-medium text-white">{server.display_name}</span>
                      </div>
                      <div className="mt-1 text-xs font-mono text-slate-500">{server.id}</div>
                      <div className="mt-2 text-sm text-slate-400">{server.notes || "No notes."}</div>
                      <div className="mt-2 text-xs text-slate-500 font-mono break-all">
                        {server.transport === "http" ? server.url : `${server.command} ${server.args.join(" ")}`}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <StatusBadge status={server.enabled ? "success" : "failed"} label={server.enabled ? "enabled" : "disabled"} />
                      <button
                        onClick={() => handleToggleServer(server.id, !server.enabled)}
                        disabled={working !== null}
                        className={`rounded-lg px-3 py-1.5 text-xs transition-colors disabled:opacity-50 ${
                          server.enabled
                            ? "border border-red-500/20 bg-red-500/10 text-red-300 hover:bg-red-500/20"
                            : "border border-emerald-500/20 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                        }`}
                      >
                        {server.enabled ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() => {
                          setSelectedServerId(server.id);
                          if (server.ready) {
                            loadServerDetails(server.id);
                          }
                        }}
                        disabled={working !== null || !server.ready}
                        className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 disabled:opacity-50"
                      >
                        Inspect
                      </button>
                    </div>
                  </div>
                  <ServerReadinessAlert enabled={server.enabled} ready={server.ready} missingEnv={server.missing_env} />
                  {server.requires_approval_for_tools.length > 0 && (
                    <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                      Approval-gated tools: {server.requires_approval_for_tools.join(", ")}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {selectedServer && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
              <h2 className="text-xl font-semibold text-white">Server Capabilities: {selectedServer.display_name}</h2>
              <ServerSetupHint serverId={selectedServer.id} />
              <div className="flex flex-col gap-4">
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <div className="text-sm font-medium text-slate-200 mb-3">Tools</div>
                  <CapabilityPanel kind="tools" payload={serverPayloads[selectedServer.id]?.tools} />
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <div className="text-sm font-medium text-slate-200 mb-3">Resources</div>
                  <CapabilityPanel kind="resources" payload={serverPayloads[selectedServer.id]?.resources} />
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <div className="text-sm font-medium text-slate-200 mb-3">Prompts</div>
                  <CapabilityPanel kind="prompts" payload={serverPayloads[selectedServer.id]?.prompts} />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Create Mutating Tool Approval</h2>
            <div className="relative">
              <select
                value={selectedServerId}
                onChange={(event) => setSelectedServerId(event.target.value)}
                className="w-full appearance-none rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 pr-10 text-sm text-slate-200 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 hover:border-slate-700 transition-colors cursor-pointer"
              >
                <option value="">Select server...</option>
                {resolution?.servers.map((server) => (
                  <option key={server.id} value={server.id} className="bg-slate-900">
                    {server.display_name}{server.enabled ? "" : " (disabled)"}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4">
                <ChevronDown className="h-4 w-4 text-slate-500" />
              </div>
            </div>
            <input
              value={toolName}
              onChange={(event) => setToolName(event.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 hover:border-slate-700 transition-colors"
              placeholder="Tool name, e.g. create_pull_request"
            />
            <textarea
              value={toolArgs}
              onChange={(event) => setToolArgs(event.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm text-slate-200 font-mono focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 hover:border-slate-700 transition-colors custom-scrollbar"
              rows={6}
              placeholder='{"title":"...", "body":"..."}'
            />
            {selectedServer && (
              <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
                Approval-gated tools configured for this server: {selectedServer.requires_approval_for_tools.join(", ") || "none"}
              </div>
            )}
            <button
              onClick={handleCreateApproval}
              disabled={working !== null || !selectedServerId || !toolName.trim() || !selectedServer?.ready}
              className="inline-flex items-center gap-2 rounded-xl bg-amber-600 hover:bg-amber-500 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
            >
              <ShieldAlert className="w-4 h-4" />
              Create Approval Artifact
            </button>
            {!enabledServers.length && (
              <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
                No MCP servers are enabled yet. Update <code>config.yml</code>, then use Reload Config.
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Approval Queue</h2>
            {approvals.length === 0 ? (
              <div className="text-sm text-slate-500">No MCP approval artifacts yet.</div>
            ) : (
              approvals.map((approval) => (
                <div key={approval.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-white">
                        {approval.server_id} / {approval.tool_name}
                      </div>
                      <div className="text-xs text-slate-500 font-mono">{approval.id}</div>
                    </div>
                    <StatusBadge
                      status={
                        approval.status === "executed"
                          ? "success"
                          : approval.status === "pending"
                            ? "pending"
                            : approval.status === "approved"
                              ? "running"
                              : "failed"
                      }
                      label={approval.status}
                    />
                  </div>
                  <pre className="whitespace-pre-wrap rounded-lg bg-slate-950 border border-slate-800 p-3 text-xs text-slate-400">
                    {JSON.stringify(approval.arguments, null, 2)}
                  </pre>
                  {approval.notes && <div className="text-sm text-slate-400">{approval.notes}</div>}
                  {approval.result_summary && <div className="text-sm text-cyan-200">{approval.result_summary}</div>}
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => runApprovalAction("approve", approval.id)}
                      disabled={working !== null || approval.status !== "pending"}
                      className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Approve
                    </button>
                    <button
                      onClick={() => runApprovalAction("reject", approval.id)}
                      disabled={working !== null || approval.status !== "pending"}
                      className="inline-flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-300 disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      Reject
                    </button>
                    <button
                      onClick={() => runApprovalAction("execute", approval.id)}
                      disabled={working !== null || approval.status !== "approved"}
                      className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-500 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                    >
                      <Rocket className="w-3.5 h-3.5" />
                      Execute
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
