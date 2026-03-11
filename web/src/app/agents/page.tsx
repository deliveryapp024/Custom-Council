"use client";

import { useEffect, useState } from "react";
import { Bot, Loader2, ShieldCheck } from "lucide-react";

import { AgentProfile, listAgents } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch((loadError: Error) => setError(loadError.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading agents...
      </div>
    );
  }

  if (error) {
    return <div className="text-red-400">{error}</div>;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-white">Agent Registry</h1>
        <p className="text-slate-400">
          The orchestrator routes tasks to these configured executors and uses the QA-capable subset for dedicated review.
        </p>
      </div>

      <div className="grid gap-4">
        {agents.map((agent) => (
          <div key={agent.id} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <Bot className="w-5 h-5 text-cyan-300" />
                  <h2 className="text-xl font-semibold text-white">{agent.display_name}</h2>
                </div>
                <div className="text-sm text-slate-400 font-mono">{agent.id}</div>
                <div className="text-sm text-slate-400">
                  Executor: <span className="text-slate-200">{agent.executor_type}</span>
                  {agent.model_override && <> | Model override: <span className="text-slate-200">{agent.model_override}</span></>}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <StatusBadge status="pending" label={agent.allowed_workflows.join(", ")} />
                {agent.qa_capable && (
                  <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    QA capable
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {agent.enabled_skills.map((skillId) => (
                <span key={`${agent.id}-${skillId}`} className="rounded-full border border-slate-800 bg-slate-950 px-3 py-1 text-xs text-slate-300">
                  {skillId}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
