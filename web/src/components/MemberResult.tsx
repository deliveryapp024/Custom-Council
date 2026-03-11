"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Terminal } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { StatusBadge } from "./StatusBadge";

interface MemberResultProps {
  name: string;
  engine: string;
  model: string;
  ok: boolean;
  durationMs: number;
  output: string;
}

export function MemberResult({ name, engine, model, ok, durationMs, output }: MemberResultProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-slate-800/60 rounded-lg overflow-hidden bg-slate-900/40 mb-3 last:mb-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-slate-800/30 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <StatusBadge status={ok ? "success" : "failed"} />
          <div>
            <div className="font-medium text-slate-200">{name}</div>
            <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5">
              <Terminal className="w-3 h-3" />
              {engine} / {model}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs font-mono text-slate-400">
            {(durationMs / 1000).toFixed(1)}s
          </div>
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-slate-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-500" />
          )}
        </div>
      </button>
      
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden border-t border-slate-800/60"
          >
            <div className="p-4 bg-slate-900/20">
              <MarkdownRenderer content={output} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
