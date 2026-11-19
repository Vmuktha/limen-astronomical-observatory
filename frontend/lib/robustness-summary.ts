import type { RobustnessRun } from './types';

export type RobustnessSummary = {
  scenario: string;
  mode: string;
  runCount: number;
  levels: number[];
  seeds: number[];
  medianSpearman: number | null;
  medianKendall: number | null;
  medianTop10Retention: number | null;
  medianTop20Retention: number | null;
  medianRankDisplacement: number | null;
  maxRankDisplacement: number | null;
  runs: RobustnessRun[];
};

export function median(values: number[]): number | null {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (sorted.length === 0) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function summarizeRobustness(runs: RobustnessRun[]): RobustnessSummary[] {
  const groups = new Map<string, RobustnessRun[]>();

  for (const run of runs) {
    const key = `${run.scenario}:${run.mode}`;
    const group = groups.get(key) ?? [];
    group.push(run);
    groups.set(key, group);
  }

  return [...groups.values()]
    .map((group) => ({
      scenario: group[0].scenario,
      mode: group[0].mode,
      runCount: group.length,
      levels: [...new Set(group.map((run) => run.level))].sort((a, b) => a - b),
      seeds: [...new Set(group.map((run) => run.seed))].sort((a, b) => a - b),
      medianSpearman: median(group.map((run) => run.spearman)),
      medianKendall: median(group.map((run) => run.kendall)),
      medianTop10Retention: median(group.map((run) => run.top10_retention)),
      medianTop20Retention: median(group.map((run) => run.top20_retention)),
      medianRankDisplacement: median(group.map((run) => run.median_abs_rank_displacement)),
      maxRankDisplacement:
        group.length > 0 ? Math.max(...group.map((run) => run.max_abs_rank_displacement)) : null,
      runs: [...group].sort((a, b) => a.level - b.level || a.seed - b.seed),
    }))
    .sort((a, b) => a.scenario.localeCompare(b.scenario) || a.mode.localeCompare(b.mode));
}
