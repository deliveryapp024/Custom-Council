import { Terminal } from "lucide-react";
import Link from "next/link";

export function Navbar() {
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
          <div className="flex gap-4">
            <Link 
              href="/" 
              className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              Dashboard
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
