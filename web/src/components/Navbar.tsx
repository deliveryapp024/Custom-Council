"use client";

import { Power, Terminal } from "lucide-react";
import Link from "next/link";

const API_BASE = "http://localhost:8000";

export function Navbar() {
  async function handleShutdown() {
    const confirmed = window.confirm(
      "Are you sure you want to stop the backend server?\n\nThis will terminate the API — the UI will stop working until you restart dev.py."
    );
    if (!confirmed) return;

    try {
      await fetch(`${API_BASE}/api/server/shutdown`, { method: "POST" });
      alert("Server is shutting down. You can close this tab.");
    } catch {
      alert("Could not reach the server (it may already be stopped).");
    }
  }

  return (
    <nav className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="bg-blue-500/10 p-2 rounded-lg border border-blue-500/20 group-hover:border-blue-500/40 transition-colors">
              <Terminal className="w-5 h-5 text-blue-400" />
            </div>
            <span className="font-semibold text-white tracking-tight">
              Council Orchestrator
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              Dashboard
            </Link>
            <Link
              href="/agents"
              className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              Agents
            </Link>
            <Link
              href="/skills"
              className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              Skills
            </Link>
            <Link
              href="/mcp"
              className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              MCP
            </Link>
            <button
              onClick={handleShutdown}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/20 hover:border-red-500/40 transition-colors"
              title="Stop the backend server"
            >
              <Power className="w-3.5 h-3.5" />
              Stop Server
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
