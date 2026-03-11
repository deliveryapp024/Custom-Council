"use client";

import { useEffect, useState, use } from "react";
import { getRun, stopRun, API_BASE, RunDetail } from "@/lib/api";
import { StageCard } from "@/components/StageCard";
import { MemberResult } from "@/components/MemberResult";
import { RankingChart } from "@/components/RankingChart";
import { ApprovalBar } from "@/components/ApprovalBar";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { StatusBadge } from "@/components/StatusBadge";
import { Terminal, Clock } from "lucide-react";

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStopping, setIsStopping] = useState(false);

  const handleStop = async () => {
    setIsStopping(true);
    try {
      await stopRun(id);
      setRun(r => r ? { ...r, status: "error", error: "Run cancelled by user." } : null);
    } catch (err: any) {
      console.error(err);
    } finally {
      setIsStopping(false);
    }
  };

  // Initial load
  useEffect(() => {
    getRun(id).then(setRun).catch(e => setError(e.message));
  }, [id]);

  // SSE Stream
  useEffect(() => {
    if (!run || ["approved", "rejected", "error", "done"].includes(run.status)) return;
    
    // Helper to safely parse JSON from SSE messages
    const safeParse = (data: any) => {
      try {
        if (!data || data === "undefined") return {};
        return JSON.parse(data);
      } catch (e) {
        console.warn("Failed to parse SSE data:", data);
        return {};
      }
    };

    // We only connect the SSE if the run is still in progress (or if we freshly loaded it)
    const eventSource = new EventSource(`${API_BASE}/runs/${id}/stream`);

    eventSource.addEventListener("snapshot", ((e: Event) => {
      const data = safeParse((e as MessageEvent).data);
      if (data.id) setRun(data);
    }) as EventListener);

    eventSource.addEventListener("stage1_start", () => {
      setRun(r => r ? { ...r, status: "stage1" } : null);
    });

    eventSource.addEventListener("stage1_member_done", ((e: Event) => {
      const result = safeParse((e as MessageEvent).data);
      setRun(r => r ? {
        ...r,
        stage1_results: [...r.stage1_results, result]
      } : null);
    }) as EventListener);

    eventSource.addEventListener("stage2_start", () => {
      setRun(r => r ? { ...r, status: "stage2" } : null);
    });

    eventSource.addEventListener("stage2_review_done", ((e: Event) => {
      const result = safeParse((e as MessageEvent).data);
      setRun(r => r ? {
        ...r,
        stage2_results: [...r.stage2_results, result]
      } : null);
    }) as EventListener);

    eventSource.addEventListener("stage2_complete", ((e: Event) => {
      const data = safeParse((e as MessageEvent).data);
      setRun(r => r ? { ...r, aggregate_rankings: data.aggregate_rankings || [] } : null);
    }) as EventListener);

    eventSource.addEventListener("stage3_start", () => {
      setRun(r => r ? { ...r, status: "stage3" } : null);
    });

    eventSource.addEventListener("stage3_complete", ((e: Event) => {
      const data = safeParse((e as MessageEvent).data);
      setRun(r => r ? { ...r, chairman_output: data.plan || "", status: "awaiting_approval" } : null);
    }) as EventListener);

    eventSource.addEventListener("error", ((e: Event) => {
      const data = safeParse((e as MessageEvent).data);
      const msg = data.message || "Unknown error occurred";
      setError(msg);
      setRun(r => r ? { ...r, status: "error", error: msg } : null);
      eventSource.close();
    }) as EventListener);

    eventSource.addEventListener("done", () => {
      eventSource.close();
    });

    return () => eventSource.close();
  }, [id, run?.status]);

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

  const isComplete = ["awaiting_approval", "approved", "rejected"].includes(run.status);
  const isFailed = run.status === "error";

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-24 relative">
      {/* Header */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 mb-8 backdrop-blur-sm shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-4">
            <div>
              <div className="text-sm font-medium text-slate-500 mb-1 flex items-center gap-2">
                <Terminal className="w-4 h-4" /> Task Directive
              </div>
              <h1 className="text-xl font-medium text-slate-200 leading-relaxed whitespace-pre-wrap">
                {run.task}
              </h1>
            </div>
            <div className="text-sm text-slate-500 font-mono bg-slate-950/50 px-3 py-1.5 rounded-md inline-block border border-slate-800/50">
              {run.project_path}
            </div>
          </div>
          
          <div className="flex flex-col items-end gap-3 shrink-0">
            <StatusBadge 
              status={
                isComplete ? "success" : 
                isFailed ? "failed" : 
                "running"
              } 
              label={run.status.replace("_", " ")}
              className="px-3 py-1 whitespace-nowrap"
            />
            {run.duration_ms > 0 && (
              <div className="flex items-center gap-1.5 text-sm text-slate-500 font-mono">
                <Clock className="w-4 h-4" />
                {(run.duration_ms / 1000).toFixed(1)}s
              </div>
            )}
            {!isComplete && !isFailed && (
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

      {/* Stage 1 */}
      <StageCard 
        title="Stage 1: Council Opinions" 
        status={run.stage1_results.length > 0 ? "success" : run.status === "stage1" ? "running" : "pending"}
      >
        {run.stage1_results.length === 0 ? (
          <div className="text-sm text-slate-500 italic py-2">Waiting for council members to begin...</div>
        ) : (
          <div>
            {run.stage1_results.map((r, i) => (
              <MemberResult 
                key={i} 
                name={r.member_name} 
                engine={r.engine} 
                model={r.model} 
                ok={r.ok} 
                durationMs={r.duration_ms} 
                output={r.error || r.response} 
              />
            ))}
          </div>
        )}
      </StageCard>

      {/* Stage 2 */}
      <StageCard 
        title="Stage 2: Cross-Review & Rankings" 
        status={run.stage2_results.length > 0 ? "success" : run.status === "stage2" ? "running" : "pending"}
      >
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
              {run.stage2_results.map((r, i) => (
                <MemberResult 
                  key={i} 
                  name={`Reviewer: ${r.reviewer_name}`} 
                  engine={r.reviewer_engine} 
                  model={r.reviewer_model} 
                  ok={r.ok} 
                  durationMs={r.duration_ms} 
                  output={r.error || r.ranking_text} 
                />
              ))}
            </div>
          )}
        </div>
      </StageCard>

      {/* Stage 3 */}
      <StageCard 
        title="Stage 3: Chairman Synthesis" 
        status={run.chairman_output ? "success" : run.status === "stage3" ? "running" : "pending"}
        defaultExpanded={true}
      >
        {!run.chairman_output ? (
          <div className="text-sm text-slate-500 italic py-2">Waiting for chairman...</div>
        ) : (
          <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-5 sm:p-8">
            <MarkdownRenderer content={run.chairman_output} />
          </div>
        )}
      </StageCard>

      {/* Action Bar (Sticky Bottom) */}
      {isComplete && (
        <ApprovalBar runId={run.id} status={run.status} />
      )}
    </div>
  );
}
