"use client";

import { useState } from "react";
import { Check, X, Edit3, Send } from "lucide-react";
import { approveRun, rejectRun, editRun } from "@/lib/api";
import { useRouter } from "next/navigation";

interface ApprovalBarProps {
  runId: string;
  status: string;
}

export function ApprovalBar({ runId, status }: ApprovalBarProps) {
  const router = useRouter();
  const [isEditing, setIsEditing] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (status === "approved" || status === "rejected") {
    return (
      <div className={`p-4 rounded-xl border flex items-center gap-3 justify-center text-sm font-medium
        ${status === "approved" ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : "bg-red-500/10 border-red-500/20 text-red-400"}`}
      >
        {status === "approved" ? <Check className="w-5 h-5" /> : <X className="w-5 h-5" />}
        Plan has been {status}
      </div>
    );
  }

  if (status !== "awaiting_approval") return null;

  const handleAction = async (action: "approve" | "reject" | "edit") => {
    setSubmitting(true);
    try {
      if (action === "approve") await approveRun(runId);
      if (action === "reject") await rejectRun(runId);
      if (action === "edit" && feedback) await editRun(runId, feedback);
      router.refresh();
      if (action === "edit") setIsEditing(false);
    } catch (e) {
      console.error(e);
      alert(`Failed to ${action}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (isEditing) {
    return (
      <div className="p-4 bg-slate-900 rounded-xl border border-slate-800 p-4 space-y-4 shadow-xl">
        <label className="block text-sm font-medium text-slate-300">
          Provide feedback for the chairman to revise the plan:
        </label>
        <textarea
          autoFocus
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 custom-scrollbar"
          rows={4}
          placeholder="E.g., Please add a step to update the README..."
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
            onClick={() => handleAction("edit")}
            disabled={submitting || !feedback.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20"
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
        Review Chairman&apos;s Final Plan
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsEditing(true)}
          disabled={submitting}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <Edit3 className="w-4 h-4" />
          Edit & Re-run
        </button>
        <button
          onClick={() => handleAction("reject")}
          disabled={submitting}
          className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 hover:border-red-500/30 text-sm font-medium rounded-lg transition-all disabled:opacity-50"
        >
          <X className="w-4 h-4" />
          Reject
        </button>
        <button
          onClick={() => handleAction("approve")}
          disabled={submitting}
          className="flex items-center gap-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50 shadow-lg shadow-emerald-500/20"
        >
          <Check className="w-4 h-4" />
          Approve Plan
        </button>
      </div>
    </div>
  );
}
