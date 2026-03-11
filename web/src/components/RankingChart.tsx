"use client";

import { AggregateRanking } from "@/lib/api";

interface RankingChartProps {
  rankings: AggregateRanking[];
}

export function RankingChart({ rankings }: RankingChartProps) {
  if (!rankings.length) return null;

  // Since rank 1 is best, max possible average is ranking length
  const maxRank = rankings.length;

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
        Consensus Ranking
      </h3>
      <div className="space-y-3">
        {rankings.map((r, i) => {
          // Calculate percentage for visual bar (lower rank = better = longer bar)
          const fillPercentage = ((maxRank - r.average_rank + 1) / maxRank) * 100;

          return (
            <div key={r.member_name} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-200">
                  {i + 1}. {r.member_name}
                </span>
                <span className="text-slate-400 tabular-nums">
                  Avg: {r.average_rank.toFixed(1)} <span className="text-slate-600">({r.rankings_count} reviews)</span>
                </span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${Math.max(10, fillPercentage)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
