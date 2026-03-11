"use client";

import { useState } from "react";
import { Check, Edit3, Send, X } from "lucide-react";

import { RunDetail, approvePlan, editRun, rejectPlan } from "@/lib/api";

interface ApprovalBarProps {
  run: RunDetail;
  onUpdated: (run: RunDetail) => void;
}

export function ApprovalBar({ run, onUpdated }: ApprovalBarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (run.status === "rejected") {
    return (
      <div className="p-4 rounded-xl border flex items-center gap-3 justify-center text-sm font-medium bg-red-500/10 border-red-500/20 text-red-400">
        <X className="w-5 h-5" />
        Plan has been rejected
      </div>
    );
  }

  if (run.status !== "awaiting_plan_approval") {
    return null;
  }

  async function handlePlanAction(action: "approve" | "reject" | "edit") {
    setSubmitting(true);
    try {
      const updatedRun =
        action === "approve"
          ? await approvePlan(run.id)
          : action === "reject"
            ? await rejectPlan(run.id, feedback)
            : await editRun(run.id, feedback);
      onUpdated(updatedRun);
      if (action === "edit") {
        setFeedback("");
        setIsEditing(false);
      }
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : `Failed to ${action} plan`);
    } finally {
      setSubmitting(false);
    }
  }

  if (isEditing) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 space-y-4 shadow-xl">
        <label className="block text-sm font-medium text-slate-300">
          Provide feedback for the chairman to revise the plan
        </label>
        <textarea
          autoFocus
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          rows={4}
          placeholder="Add missing steps, tighten scope, or ask for a different task breakdown."
        />
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setIsEditing(false)}
            className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={() => handlePlanAction("edit")}
            disabled={submitting || !feedback.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            Submit Revision
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-2 bg-slate-900/80 backdrop-blur-md rounded-xl border border-slate-800 flex items-center justify-between shadow-xl sticky bottom-4">
      <div className="px-4 text-sm font-medium text-slate-300">
        Gate 1: Approve the final plan before task generation starts
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsEditing(true)}
          disabled={submitting}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <Edit3 className="w-4 h-4" />
          Edit
        </button>
        <button
          onClick={() => handlePlanAction("reject")}
          disabled={submitting}
          className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 text-sm font-medium rounded-lg transition-all disabled:opacity-50"
        >
          <X className="w-4 h-4" />
          Reject
        </button>
        <button
          onClick={() => handlePlanAction("approve")}
          disabled={submitting}
          className="flex items-center gap-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50"
        >
          <Check className="w-4 h-4" />
          Approve Plan
        </button>
      </div>
    </div>
  );
}
