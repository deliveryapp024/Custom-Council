"use client";

import { ReactNode, useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Clock, PlayCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { StatusBadge, StatusType } from "./StatusBadge";

interface StageCardProps {
  title: string;
  status: StatusType;
  children: ReactNode;
  defaultExpanded?: boolean;
}

export function StageCard({ title, status, children, defaultExpanded = true }: StageCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Auto-expand if running
  if (status === "running" && !expanded) {
    setExpanded(true);
  }

  const statusIcons = {
    running: <PlayCircle className="w-5 h-5 text-blue-400 animate-pulse" />,
    success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    failed: <CheckCircle2 className="w-5 h-5 text-red-400" />, // using CheckCircle as base but red
    pending: <Clock className="w-5 h-5 text-slate-500" />,
    timeout: <Clock className="w-5 h-5 text-yellow-500" />,
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm overflow-hidden transition-all duration-200 hover:border-slate-700/50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 bg-slate-800/20 hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          {statusIcons[status]}
          <h2 className="text-lg font-medium text-slate-200 tracking-tight">{title}</h2>
        </div>
        <div className="flex items-center gap-4">
          <StatusBadge status={status} />
          <div className="p-1 rounded-md bg-slate-800/50 text-slate-400">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="p-4 border-t border-slate-800/50">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
