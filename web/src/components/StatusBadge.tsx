import React from "react";
import clsx from "clsx";
import { CheckCircle2, Circle, Clock, Loader2, XCircle } from "lucide-react";

export type StatusType = "running" | "success" | "failed" | "pending" | "timeout";

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
  label?: string;
}

export function StatusBadge({ status, className, label }: StatusBadgeProps) {
  const baseClasses = "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border";

  const statusConfig = {
    running: {
      classes: "bg-blue-500/10 text-blue-400 border-blue-500/20",
      icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
      defaultLabel: "Running"
    },
    success: {
      classes: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      defaultLabel: "Success"
    },
    failed: {
      classes: "bg-red-500/10 text-red-400 border-red-500/20",
      icon: <XCircle className="w-3.5 h-3.5" />,
      defaultLabel: "Failed"
    },
    pending: {
      classes: "bg-slate-500/10 text-slate-400 border-slate-500/20",
      icon: <Circle className="w-3.5 h-3.5" />,
      defaultLabel: "Pending"
    },
    timeout: {
      classes: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
      icon: <Clock className="w-3.5 h-3.5" />,
      defaultLabel: "Timeout"
    }
  };

  const config = statusConfig[status];

  return (
    <span className={clsx(baseClasses, config.classes, className)}>
      {config.icon}
      {label || config.defaultLabel}
    </span>
  );
}
