"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Clock, FolderGit2, ShieldCheck, Terminal } from "lucide-react";

import { ApprovalBar } from "@/components/ApprovalBar";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { MemberResult } from "@/components/MemberResult";
import { RankingChart } from "@/components/RankingChart";
import { StageCard } from "@/components/StageCard";
import { StatusBadge } from "@/components/StatusBadge";
import { API_BASE, RunDetail, getRun, stopRun } from "@/lib/api";

function mapRunStatus(status: RunDetail["status"]) {
  if (status === "completed") {
    return "success" as const;
  }
  if (["failed", "rejected"].includes(status)) {
    return "failed" as const;
  }
  if (
    [
      "awaiting_plan_approval",
      "task_graph_ready",
      "awaiting_execution_approval",
      "awaiting_commit_approval",
      "awaiting_completion_approval",
    ].includes(status)
  ) {
    return "pending" as const;
  }
  return "running" as const;
}

function mapTaskStatus(status: string) {
  if (status === "completed") {
    return "success" as const;
  }
  if (["failed", "rejected", "execution_retry_needed"].includes(status)) {
    return "failed" as const;
  }
  if (["awaiting_assignment", "awaiting_execution_approval", "awaiting_completion_approval"].includes(status)) {
    return "pending" as const;
  }
  return "running" as const;
}

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStopping, setIsStopping] = useState(false);

  useEffect(() => {
    getRun(id).then(setRun).catch((err: Error) => setError(err.message));
  }, [id]);

  useEffect(() => {
    if (!run) {
      return;
    }
    if (["completed", "rejected", "failed"].includes(run.status)) {
      return;
    }

    const source = new EventSource(`${API_BASE}/runs/${id}/stream`);
    const onSnapshot = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as RunDetail;
        if (payload.id) {
          setRun(payload);
        }
      } catch (parseError) {
        console.warn("Failed to parse run snapshot", parseError);
      }
    };
    const onError = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data);
        if (payload.message) {
          setError(payload.message);
        }
      } catch {
        setError("Run stream failed");
      }
    };

    source.addEventListener("snapshot", onSnapshot as EventListener);
    source.addEventListener("error", onError as EventListener);
    source.addEventListener("done", () => source.close());

    return () => source.close();
  }, [id, run?.status]);

  async function handleStop() {
    setIsStopping(true);
    try {
      await stopRun(id);
      const refreshed = await getRun(id);
      setRun(refreshed);
    } catch (stopError) {
      console.error(stopError);
    } finally {
      setIsStopping(false);
    }
  }

  if (error && !run) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center space-y-4">
        <div className="text-red-500 font-medium text-lg">Failed to load run</div>
        <div className="text-slate-400">{error}</div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-pulse flex gap-2 items-center text-slate-400">
          <Terminal className="w-5 h-5 animate-bounce" /> Loading council data...
        </div>
      </div>
    );
  }

  const planReady = Boolean(run.chairman_output);
  const canStop = !["completed", "rejected", "failed"].includes(run.status);

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-24">
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 backdrop-blur-sm shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div className="space-y-4">
            <div>
              <div className="text-sm font-medium text-slate-500 mb-1 flex items-center gap-2">
                <Terminal className="w-4 h-4" /> Task Directive
              </div>
              <h1 className="text-xl font-medium text-slate-200 leading-relaxed whitespace-pre-wrap">{run.task}</h1>
            </div>
            <div className="flex flex-wrap gap-3 text-sm text-slate-400">
              <span className="font-mono bg-slate-950/50 px-3 py-1.5 rounded-md border border-slate-800/50">{run.id}</span>
              <span className="font-mono bg-slate-950/50 px-3 py-1.5 rounded-md border border-slate-800/50 flex items-center gap-2">
                <FolderGit2 className="w-4 h-4" />
                {run.project_path}
              </span>
              {run.workspace_path && (
                <span className="font-mono bg-slate-950/50 px-3 py-1.5 rounded-md border border-slate-800/50">
                  {run.workspace_path}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end gap-3 shrink-0">
            <StatusBadge status={mapRunStatus(run.status)} label={run.status.replaceAll("_", " ")} className="px-3 py-1 whitespace-nowrap" />
            {run.duration_ms > 0 && (
              <div className="flex items-center gap-1.5 text-sm text-slate-500 font-mono">
                <Clock className="w-4 h-4" />
                {(run.duration_ms / 1000).toFixed(1)}s
              </div>
            )}
            {canStop && (
              <button
                onClick={handleStop}
                disabled={isStopping}
                className="text-xs text-red-400 hover:text-red-300 border border-red-500/20 hover:bg-red-500/10 px-3 py-1 rounded-full transition-colors disabled:opacity-50"
              >
                {isStopping ? "Stopping..." : "Stop Run"}
              </button>
            )}
          </div>
        </div>
      </div>

      <StageCard title="Stage 1: Council Opinions" status={run.stage1_results.length > 0 ? "success" : run.status === "stage1" ? "running" : "pending"}>
        {run.stage1_results.length === 0 ? (
          <div className="text-sm text-slate-500 italic py-2">Waiting for council members to begin...</div>
        ) : (
          <div>
            {run.stage1_results.map((result) => (
              <MemberResult
                key={`${result.member_name}-${result.model}`}
                name={result.member_name}
                engine={result.engine}
                model={result.model}
                ok={result.ok}
                durationMs={result.duration_ms}
                output={result.error || result.response}
              />
            ))}
          </div>
        )}
      </StageCard>

      <StageCard title="Stage 2: Cross-Review & Rankings" status={run.stage2_results.length > 0 ? "success" : run.status === "stage2" ? "running" : "pending"}>
        <div className="space-y-6">
          {run.aggregate_rankings.length > 0 && (
            <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-5">
              <RankingChart rankings={run.aggregate_rankings} />
            </div>
          )}
          {run.stage2_results.length === 0 ? (
            <div className="text-sm text-slate-500 italic py-2">Waiting for cross-reviews...</div>
          ) : (
            <div className="space-y-3">
              <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Individual Reviews</h4>
              {run.stage2_results.map((result) => (
                <MemberResult
                  key={`${result.reviewer_name}-${result.reviewer_model}`}
                  name={`Reviewer: ${result.reviewer_name}`}
                  engine={result.reviewer_engine}
                  model={result.reviewer_model}
                  ok={result.ok}
                  durationMs={result.duration_ms}
                  output={result.error || result.ranking_text}
                />
              ))}
            </div>
          )}
        </div>
      </StageCard>

      <StageCard title="Stage 3: Chairman Synthesis" status={planReady ? "success" : run.status === "stage3" ? "running" : "pending"} defaultExpanded={true}>
        {!planReady ? (
          <div className="text-sm text-slate-500 italic py-2">Waiting for chairman...</div>
        ) : (
          <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-5 sm:p-8">
            <MarkdownRenderer content={run.chairman_output} />
          </div>
        )}
      </StageCard>

      <StageCard title="Task Graph & Routing" status={run.tasks.length > 0 ? "success" : run.status === "task_graph_ready" ? "running" : "pending"} defaultExpanded={run.tasks.length > 0}>
        {run.tasks.length === 0 ? (
          <div className="text-sm text-slate-500 italic py-2">
            Tasks will appear here after the plan is approved.
          </div>
        ) : (
          <div className="space-y-4">
            {run.tasks.map((task) => (
              <Link
                key={task.id}
                href={`/tasks/${task.id}`}
                className="block rounded-xl border border-slate-800 bg-slate-950/40 hover:border-slate-700 transition-colors p-4"
              >
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-3 flex-wrap">
                      <h3 className="text-base font-medium text-white">{task.title}</h3>
                      <StatusBadge status={mapTaskStatus(task.status)} label={task.status.replaceAll("_", " ")} />
                    </div>
                    <p className="text-sm text-slate-400 whitespace-pre-wrap">{task.description}</p>
                    <div className="flex flex-wrap gap-2 text-xs text-slate-400">
                      <span className="px-2 py-1 rounded-full border border-slate-800 bg-slate-900/50">
                        Priority {task.priority}
                      </span>
                      {task.recommended_agent_id && (
                        <span className="px-2 py-1 rounded-full border border-cyan-500/20 bg-cyan-500/10 text-cyan-300">
                          Recommended: {task.recommended_agent_id}
                        </span>
                      )}
                      {task.selected_agent_id && (
                        <span className="px-2 py-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-300">
                          Selected: {task.selected_agent_id}
                        </span>
                      )}
                      {task.recommended_skills.map((skillId) => (
                        <span key={`${task.id}-${skillId}`} className="px-2 py-1 rounded-full border border-slate-800 bg-slate-900/50">
                          {skillId}
                        </span>
                      ))}
                    </div>
                    {task.routing_reason && <div className="text-xs text-slate-500">{task.routing_reason}</div>}
                  </div>

                  <div className="text-xs text-slate-500 space-y-1 shrink-0">
                    <div>{task.assignments.length} assignments</div>
                    <div>{task.attempts.length} execution attempts</div>
                    <div>{task.qa_reports.length} QA reports</div>
                    {task.branch_name && <div className="font-mono">{task.branch_name}</div>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </StageCard>

      <StageCard title="Approval History" status={run.approvals.length > 0 ? "success" : "pending"}>
        {run.approvals.length === 0 ? (
          <div className="text-sm text-slate-500 italic py-2">No approvals recorded yet.</div>
        ) : (
          <div className="space-y-3">
            {run.approvals.map((approval) => (
              <div key={approval.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-cyan-400" />
                    <span className="text-sm font-medium text-slate-200">
                      {approval.gate} / {approval.decision}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">{new Date(approval.created_at).toLocaleString()}</span>
                </div>
                {approval.task_id && <div className="mt-2 text-xs text-slate-500">Task: {approval.task_id}</div>}
                {approval.notes && <div className="mt-2 text-sm text-slate-400 whitespace-pre-wrap">{approval.notes}</div>}
              </div>
            ))}
          </div>
        )}
      </StageCard>

      <ApprovalBar run={run} onUpdated={setRun} />
    </div>
  );
}
