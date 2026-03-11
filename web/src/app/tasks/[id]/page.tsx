"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ArrowLeft, Check, ClipboardCheck, Loader2, Play, RefreshCcw, X } from "lucide-react";

import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { StatusBadge } from "@/components/StatusBadge";
import {
  AgentProfile,
  SkillDefinition,
  TaskRecord,
  approveCompletion,
  approveExecution,
  assignTask,
  executeTask,
  getTask,
  listAgents,
  listSkills,
  rejectCompletion,
  rejectExecution,
  runTaskQa,
} from "@/lib/api";

function mapTaskStatus(status: TaskRecord["status"]) {
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

export default function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshTask() {
    const latest = await getTask(id);
    setTask(latest);
    setSelectedAgentId(latest.selected_agent_id || latest.recommended_agent_id || "");
    setSelectedSkills(latest.selected_skills.length > 0 ? latest.selected_skills : latest.recommended_skills);
  }

  useEffect(() => {
    Promise.all([refreshTask(), listAgents(), listSkills()])
      .then((results) => {
        setAgents(results[1]);
        setSkills(results[2]);
      })
      .catch((loadError: Error) => setError(loadError.message));
  }, [id]);

  async function runAction(action: string, fn: () => Promise<unknown>) {
    setWorking(action);
    try {
      await fn();
      await refreshTask();
    } catch (actionError) {
      console.error(actionError);
      alert(actionError instanceof Error ? actionError.message : `Failed to ${action}`);
    } finally {
      setWorking(null);
    }
  }

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? null;
  const allowedSkills = selectedAgent
    ? skills.filter((skill) => selectedAgent.enabled_skills.includes(skill.id))
    : skills;

  if (error && !task) {
    return <div className="text-red-400">{error}</div>;
  }

  if (!task) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading task...
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-16">
      <div className="flex items-center justify-between gap-4">
        <Link href={`/runs/${task.run_id}`} className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" />
          Back to run
        </Link>
        <StatusBadge status={mapTaskStatus(task.status)} label={task.status.replaceAll("_", " ")} />
      </div>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-white">{task.title}</h1>
            <div className="text-sm text-slate-400 whitespace-pre-wrap">{task.description}</div>
          </div>
          <div className="text-xs text-slate-500 space-y-1 text-right">
            <div>Priority {task.priority}</div>
            {task.branch_name && <div className="font-mono">{task.branch_name}</div>}
            {task.worktree_path && <div className="font-mono break-all">{task.worktree_path}</div>}
          </div>
        </div>

        {task.routing_reason && (
          <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
            {task.routing_reason}
          </div>
        )}

        <div className="flex flex-wrap gap-2 text-xs text-slate-400">
          {task.recommended_agent_id && (
            <span className="px-2 py-1 rounded-full border border-cyan-500/20 bg-cyan-500/10 text-cyan-300">
              Recommended agent: {task.recommended_agent_id}
            </span>
          )}
          {task.recommended_skills.map((skillId) => (
            <span key={skillId} className="px-2 py-1 rounded-full border border-slate-800 bg-slate-900/50">
              {skillId}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-white">Assignment & Skills</h2>
          <p className="text-sm text-slate-400 mt-1">
            Choose the executor and confirm the skills this task should use before the execution approval gate.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <label className="space-y-2">
            <span className="block text-sm font-medium text-slate-300">Selected agent</span>
            <select
              value={selectedAgentId}
              onChange={(event) => {
                const nextAgentId = event.target.value;
                setSelectedAgentId(nextAgentId);
                const nextAgent = agents.find((agent) => agent.id === nextAgentId);
                if (nextAgent) {
                  setSelectedSkills((current) => current.filter((skillId) => nextAgent.enabled_skills.includes(skillId)));
                }
              }}
              className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              <option value="">Select an agent</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.display_name} ({agent.executor_type})
                </option>
              ))}
            </select>
          </label>

          <div className="space-y-2">
            <span className="block text-sm font-medium text-slate-300">Selected skills</span>
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-2 max-h-56 overflow-y-auto">
              {allowedSkills.length === 0 ? (
                <div className="text-sm text-slate-500">No skills available for the selected agent.</div>
              ) : (
                allowedSkills.map((skill) => (
                  <label key={skill.id} className="flex items-start gap-3 text-sm text-slate-300">
                    <input
                      type="checkbox"
                      checked={selectedSkills.includes(skill.id)}
                      onChange={(event) =>
                        setSelectedSkills((current) =>
                          event.target.checked
                            ? [...current, skill.id]
                            : current.filter((skillId) => skillId !== skill.id),
                        )
                      }
                      className="mt-1"
                    />
                    <span>
                      <span className="font-medium text-slate-200">{skill.name}</span>
                      <span className="block text-slate-500">{skill.description}</span>
                    </span>
                  </label>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => runAction("assign task", () => assignTask(task.id, selectedAgentId, selectedSkills))}
            disabled={working !== null || !selectedAgentId}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            <ClipboardCheck className="w-4 h-4" />
            Save Assignment
          </button>
          <button
            onClick={() => runAction("refresh task", refreshTask)}
            disabled={working !== null}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-200 disabled:opacity-50"
          >
            <RefreshCcw className={`w-4 h-4 ${working === "refresh task" ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">Human Gates</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => runAction("approve execution", () => approveExecution(task.id))}
            disabled={working !== null || !task.selected_agent_id || !["awaiting_execution_approval", "execution_retry_needed"].includes(task.status)}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            Approve Execution
          </button>
          <button
            onClick={() => runAction("reject execution", () => rejectExecution(task.id))}
            disabled={working !== null || !task.selected_agent_id || !["awaiting_execution_approval", "execution_retry_needed"].includes(task.status)}
            className="inline-flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-300 disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            Reject Execution
          </button>
          <button
            onClick={() => runAction("execute task", () => executeTask(task.id))}
            disabled={working !== null || !task.selected_agent_id || !["awaiting_execution_approval", "execution_retry_needed"].includes(task.status)}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {working === "execute task" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Execute Task
          </button>
          <button
            onClick={() => runAction("run qa", () => runTaskQa(task.id))}
            disabled={working !== null || task.attempts.length === 0 || !["qa_review", "execution_retry_needed", "awaiting_completion_approval"].includes(task.status)}
            className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-2.5 text-sm font-medium text-cyan-200 disabled:opacity-50"
          >
            <ClipboardCheck className="w-4 h-4" />
            Run QA
          </button>
          <button
            onClick={() => runAction("approve completion", () => approveCompletion(task.id))}
            disabled={working !== null || task.status !== "awaiting_completion_approval"}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            Approve Completion
          </button>
          <button
            onClick={() => runAction("reject completion", () => rejectCompletion(task.id))}
            disabled={working !== null || task.status !== "awaiting_completion_approval"}
            className="inline-flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-300 disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            Reject Completion
          </button>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">Execution Attempts</h2>
          {task.attempts.length === 0 ? (
            <div className="text-sm text-slate-500">No execution attempts yet.</div>
          ) : (
            task.attempts.map((attempt) => (
              <div key={attempt.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-slate-200">
                    Attempt {attempt.attempt_no} by {attempt.agent_id}
                  </div>
                  <StatusBadge
                    status={attempt.exit_code === 0 && attempt.test_result === "passed" ? "success" : attempt.exit_code === null ? "running" : "failed"}
                    label={attempt.test_result}
                  />
                </div>
                <div className="text-xs text-slate-500">
                  Exit code: {attempt.exit_code ?? "running"} | Tests: {attempt.test_result}
                </div>
                {attempt.stdout && (
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">stdout</div>
                    <pre className="whitespace-pre-wrap rounded-lg bg-slate-950 border border-slate-800 p-3 text-xs text-slate-300">{attempt.stdout}</pre>
                  </div>
                )}
                {attempt.stderr && (
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">stderr</div>
                    <pre className="whitespace-pre-wrap rounded-lg bg-slate-950 border border-slate-800 p-3 text-xs text-red-200">{attempt.stderr}</pre>
                  </div>
                )}
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">prompt</div>
                  <div className="rounded-lg bg-slate-950 border border-slate-800 p-3 text-sm text-slate-300">
                    <MarkdownRenderer content={attempt.prompt} />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">QA Reports</h2>
          {task.qa_reports.length === 0 ? (
            <div className="text-sm text-slate-500">No QA reports yet.</div>
          ) : (
            task.qa_reports.map((report) => (
              <div key={report.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-slate-200">{report.agent_id}</div>
                  <StatusBadge status={report.recommendation === "pass" ? "success" : "failed"} label={report.recommendation} />
                </div>
                <div className="text-sm text-slate-300">{report.summary}</div>
                {report.findings.length > 0 && (
                  <div className="space-y-2">
                    {report.findings.map((finding, index) => (
                      <div key={`${report.id}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium text-slate-200">{finding.title}</div>
                          <StatusBadge status={["critical", "high"].includes(finding.severity) ? "failed" : "pending"} label={finding.severity} />
                        </div>
                        <div className="mt-2 text-sm text-slate-400">{finding.details}</div>
                        {finding.suggested_fix && <div className="mt-2 text-sm text-cyan-200">{finding.suggested_fix}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">Assignments</h2>
          {task.assignments.length === 0 ? (
            <div className="text-sm text-slate-500">No assignments recorded yet.</div>
          ) : (
            task.assignments.map((assignment) => (
              <div key={assignment.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-slate-200">{assignment.agent_id}</div>
                  <StatusBadge status={assignment.approval_state === "approved" ? "success" : assignment.approval_state === "rejected" ? "failed" : "pending"} label={assignment.approval_state} />
                </div>
                <div className="mt-2 text-sm text-slate-400">{assignment.selected_skills.join(", ") || "No skills selected"}</div>
              </div>
            ))
          )}
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">Approvals</h2>
          {task.approvals.length === 0 ? (
            <div className="text-sm text-slate-500">No approvals recorded yet.</div>
          ) : (
            task.approvals.map((approval) => (
              <div key={approval.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-slate-200">
                    {approval.gate} / {approval.decision}
                  </div>
                  <span className="text-xs text-slate-500">{new Date(approval.created_at).toLocaleString()}</span>
                </div>
                {approval.notes && <div className="mt-2 text-sm text-slate-400">{approval.notes}</div>}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
