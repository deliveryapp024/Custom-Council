"use client";

import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { SkillDefinition, listSkills } from "@/lib/api";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSkills()
      .then(setSkills)
      .catch((loadError: Error) => setError(loadError.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading skills...
      </div>
    );
  }

  if (error) {
    return <div className="text-red-400">{error}</div>;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-white">Skill Catalog</h1>
        <p className="text-slate-400">
          Council task routing recommends these registered skills, and execution and QA prompts pull their preambles into the workflow.
        </p>
      </div>

      <div className="grid gap-4">
        {skills.map((skill) => (
          <div key={skill.id} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <Sparkles className="w-5 h-5 text-amber-300" />
                  <h2 className="text-xl font-semibold text-white">{skill.name}</h2>
                </div>
                <div className="text-sm text-slate-400 font-mono">{skill.id}</div>
                {skill.source && <div className="text-xs text-slate-500 uppercase tracking-wider">{skill.source}</div>}
                <p className="text-sm text-slate-300">{skill.description}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {skill.tags.map((tag) => (
                  <span key={`${skill.id}-${tag}`} className="rounded-full border border-slate-800 bg-slate-950 px-3 py-1 text-xs text-slate-300">
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            {skill.prompt_preamble && (
              <div className="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3">
                <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Prompt preamble</div>
                <div className="text-sm text-slate-300 whitespace-pre-wrap">{skill.prompt_preamble}</div>
              </div>
            )}

            {skill.source_path && (
              <div className="text-xs text-slate-500 font-mono break-all">{skill.source_path}</div>
            )}

            <div className="flex flex-wrap gap-2">
              {skill.allowed_agents.map((agentId) => (
                <span key={`${skill.id}-${agentId}`} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-200">
                  {agentId}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
