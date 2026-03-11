"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderGit2, Loader2, Play } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

import { RunSummary, listRuns, startRun } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

function mapRunStatus(status: string) {
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

export default function Dashboard() {
  const router = useRouter();
  const [task, setTask] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(console.error)
      .finally(() => setLoadingRuns(false));
  }, []);

  async function handleStartRun(event: React.FormEvent) {
    event.preventDefault();
    if (!task || !projectPath) {
      return;
    }

    setIsStarting(true);
    try {
      const run = await startRun(task, projectPath);
      router.push(`/runs/${run.id}`);
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : "Failed to start run");
      setIsStarting(false);
    }
  }

  return (
    <div className="space-y-12 max-w-5xl mx-auto">
      <section className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-cyan-500 to-emerald-500 opacity-60" />

        <h2 className="text-2xl font-semibold tracking-tight text-white mb-6">Start New Council Run</h2>

        <form onSubmit={handleStartRun} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="task" className="block text-sm font-medium text-slate-300">
              Task Description
            </label>
            <textarea
              id="task"
              value={task}
              onChange={(event) => setTask(event.target.value)}
              placeholder="Refactor authentication, split work into tasks, and verify each task before completion."
              className="w-full bg-slate-950/50 border border-slate-800 rounded-xl p-4 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-y text-base"
              rows={4}
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="projectPath" className="block text-sm font-medium text-slate-300">
              Project Path
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <FolderGit2 className="w-5 h-5 text-slate-500" />
              </div>
              <input
                type="text"
                id="projectPath"
                value={projectPath}
                onChange={(event) => setProjectPath(event.target.value)}
                placeholder="C:\\Projects\\my-app"
                className="w-full pl-11 bg-slate-950/50 border border-slate-800 rounded-xl p-3.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-base"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isStarting || !task || !projectPath}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20"
          >
            {isStarting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
            {isStarting ? "Summoning Council..." : "Run Council"}
          </button>
        </form>
      </section>

      <section className="space-y-6">
        <h2 className="text-xl font-semibold tracking-tight text-white flex items-center gap-2">
          Recent Runs
          {loadingRuns && <Loader2 className="w-4 h-4 animate-spin text-slate-500" />}
        </h2>

        {!loadingRuns && runs.length === 0 ? (
          <div className="text-center py-12 px-4 rounded-xl border border-dashed border-slate-800 text-slate-500">
            No council runs found. Start one above.
          </div>
        ) : (
          <div className="grid gap-4">
            {runs.map((run) => (
              <div
                key={run.id}
                onClick={() => router.push(`/runs/${run.id}`)}
                className="group cursor-pointer bg-slate-900/30 border border-slate-800/60 rounded-xl p-5 hover:bg-slate-800/40 hover:border-slate-700 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-200 truncate pr-4">{run.task}</div>
                  <div className="text-xs text-slate-500 flex items-center gap-3">
                    <span className="font-mono">{run.id}</span>
                    <span>•</span>
                    <span>{formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}</span>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right text-xs text-slate-500 hidden sm:block">
                    <div>{run.duration_ms > 0 ? `${(run.duration_ms / 1000).toFixed(1)}s` : "—"}</div>
                    <div>{run.members_ok} / {run.members_total} members</div>
                    <div>{run.completed_tasks} / {run.task_count} tasks</div>
                  </div>
                  <StatusBadge status={mapRunStatus(run.status)} label={run.status.replaceAll("_", " ")} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
