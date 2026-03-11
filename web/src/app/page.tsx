"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { startRun, listRuns, RunSummary } from "@/lib/api";
import { Play, FolderGit2, Loader2 } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDistanceToNow } from "date-fns";

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

  const handleStartRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task || !projectPath) return;

    setIsStarting(true);
    try {
      const res = await startRun(task, projectPath);
      router.push(`/runs/${res.id}`);
    } catch (err) {
      console.error(err);
      alert("Failed to start run");
      setIsStarting(false);
    }
  };

  return (
    <div className="space-y-12 max-w-5xl mx-auto">
      {/* Run Form */}
      <section className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 opacity-50" />
        
        <h2 className="text-2xl font-semibold tracking-tight text-white mb-6">Start New Council Run</h2>
        
        <form onSubmit={handleStartRun} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="task" className="block text-sm font-medium text-slate-300">
              Task Description
            </label>
            <textarea
              id="task"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="E.g., Refactor the authentication middleware to use JWT tokens..."
              className="w-full bg-slate-950/50 border border-slate-800 rounded-xl p-4 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 custom-scrollbar resize-y text-base"
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
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="/Users/arali/projects/my-app"
                className="w-full pl-11 bg-slate-950/50 border border-slate-800 rounded-xl p-3.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-base"
                required
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isStarting || !task || !projectPath}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20"
            >
              {isStarting ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Play className="w-5 h-5 fill-current" />
              )}
              {isStarting ? "Summoning Council..." : "Run Council"}
            </button>
          </div>
        </form>
      </section>

      {/* Run History */}
      <section className="space-y-6">
        <h2 className="text-xl font-semibold tracking-tight text-white flex items-center gap-2">
          Recent Runs
          {loadingRuns && <Loader2 className="w-4 h-4 animate-spin text-slate-500" />}
        </h2>

        {!loadingRuns && runs.length === 0 ? (
          <div className="text-center py-12 px-4 rounded-xl border border-dashed border-slate-800 text-slate-500">
            No council runs found. Start one above!
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
                  <div className="text-sm font-medium text-slate-200 truncate pr-4">
                    {run.task}
                  </div>
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
                  </div>
                  <StatusBadge 
                    status={
                      ["approved", "success"].includes(run.status) ? "success" :
                      ["rejected", "error"].includes(run.status) ? "failed" :
                      ["awaiting_approval"].includes(run.status) ? "pending" :
                      "running"
                    }
                    label={run.status.replace("_", " ")}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
