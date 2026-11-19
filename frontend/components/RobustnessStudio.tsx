'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { median, summarizeRobustness } from '../lib/robustness-summary';
import type { RobustnessRun } from '../lib/types';

type Mode = RobustnessRun['mode'];
type Props = { runs: RobustnessRun[] };

const modeLabels: Record<Mode, string> = {
  multimodal: 'Multimodal',
  spectral: 'Spectral',
  image: 'Image',
};

const familyLabels: Record<string, string> = {
  image_blur: 'Image blur',
  image_mask: 'Image masking',
  image_noise: 'Image noise',
  spectral_coverage: 'Spectral coverage',
  spectral_mask: 'Spectral masking',
  spectral_noise: 'Spectral noise',
};

const fmt = (value: number | null, digits = 3) =>
  value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits);

const runKey = (run: RobustnessRun) =>
  `${run.scenario}:${run.mode}:${run.level}:${run.seed}`;

export default function RobustnessStudio({ runs }: Props) {
  const [mode, setMode] = useState<Mode>('multimodal');
  const [familyFilter, setFamilyFilter] = useState('all');
  const [modeFilter, setModeFilter] = useState('all');
  const [levelFilter, setLevelFilter] = useState('all');
  const [seedFilter, setSeedFilter] = useState('all');
  const [selectedRun, setSelectedRun] = useState<RobustnessRun | null>(null);

  const summaries = useMemo(() => summarizeRobustness(runs), [runs]);
  const visibleSummaries = summaries.filter((summary) => summary.mode === mode);
  const modeRuns = runs.filter((run) => run.mode === mode);
  const globalSpearman = median(modeRuns.map((run) => run.spearman));
  const globalTop20 = median(modeRuns.map((run) => run.top20_retention));
  const familyOptions = [...new Set(runs.map((run) => run.scenario))].sort();
  const levelOptions = [...new Set(runs.map((run) => run.level))].sort((a, b) => a - b);
  const seedOptions = [...new Set(runs.map((run) => run.seed))].sort((a, b) => a - b);

  const filteredRuns = runs
    .filter((run) => familyFilter === 'all' || run.scenario === familyFilter)
    .filter((run) => modeFilter === 'all' || run.mode === modeFilter)
    .filter((run) => levelFilter === 'all' || String(run.level) === levelFilter)
    .filter((run) => seedFilter === 'all' || String(run.seed) === seedFilter)
    .sort((a, b) => a.scenario.localeCompare(b.scenario) || a.mode.localeCompare(b.mode) || a.level - b.level || a.seed - b.seed);

  const chartData = visibleSummaries.map((summary) => ({
    family: familyLabels[summary.scenario] ?? summary.scenario,
    scenario: summary.scenario,
    medianSpearman: summary.medianSpearman,
    medianTop20: summary.medianTop20Retention,
  }));

  return (
    <section id="robustness" className="card p-5 sm:p-6" aria-labelledby="robustness-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label">Phase 5 / robustness studio</p>
          <h2 id="robustness-title" className="mt-1 text-xl">Controlled degradation stability</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-mute">
            Each run perturbs one input family and refits the pipeline with fixed Phase 3 hyperparameters. The comparison measures ranking sensitivity under these controlled perturbations; it is not a scientific accuracy test.
          </p>
        </div>
        <span className="rounded-full border border-[#365471] px-3 py-1.5 font-mono text-xs text-cyan">
          {runs.length} recorded runs
        </span>
      </div>

      <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Filter robustness summaries by baseline">
        {(['multimodal', 'spectral', 'image'] as const).map((value) => {
          const count = runs.filter((run) => run.mode === value).length;
          return (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
              className={`rounded-full border px-4 py-2 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan ${
                mode === value
                  ? 'border-cyan bg-[#122640] text-cyan'
                  : 'border-[#365471] text-[#c7d4e4] hover:border-cyan'
              }`}
            >
              {modeLabels[value]} <span className="ml-1 font-mono text-xs opacity-70">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
          <p className="label">Median Spearman correlation</p>
          <p className="mt-2 text-2xl font-semibold text-cyan">{fmt(globalSpearman)}</p>
          <p className="mt-1 text-xs text-mute">Across the {modeRuns.length} {modeLabels[mode].toLowerCase()} runs; higher means closer rank ordering.</p>
        </div>
        <div className="rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
          <p className="label">Median top-20 retention</p>
          <p className="mt-2 text-2xl font-semibold text-cyan">{fmt(globalTop20, 1)} / 20</p>
          <p className="mt-1 text-xs text-mute">Overlap with the original Phase 3 top 20, measured per run.</p>
        </div>
      </div>

      {visibleSummaries.length ? (
        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <ChartPanel
            title="Median rank correlation"
            subtitle="Spearman ρ · 1 indicates identical rank ordering"
            data={chartData}
            dataKey="medianSpearman"
            domain={[0, 1]}
            color="#83d6d2"
            formatter={(value) => fmt(value)}
          />
          <ChartPanel
            title="Median top-20 retention"
            subtitle="Number of original top-20 observations retained"
            data={chartData}
            dataKey="medianTop20"
            domain={[0, 20]}
            color="#f2c977"
            formatter={(value) => `${fmt(value, 1)} / 20`}
          />
        </div>
      ) : (
        <p className="mt-6 rounded-lg border border-dashed border-[#365471] p-6 text-sm text-mute">
          No recorded runs are available for this baseline.
        </p>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {visibleSummaries.map((summary) => (
          <article key={`${summary.scenario}:${summary.mode}`} className="rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-medium">{familyLabels[summary.scenario] ?? summary.scenario}</h3>
                <p className="mt-1 text-xs text-mute">
                  {summary.runCount} runs · levels {summary.levels.join(', ')} · seeds {summary.seeds.join(', ')}
                </p>
              </div>
              <span className="rounded border border-[#29415d] px-2 py-1 text-[10px] uppercase tracking-wide text-mute">
                {modeLabels[mode]}
              </span>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-3 text-xs">
              <div><dt className="label">Median ρ</dt><dd className="mt-1 text-cyan">{fmt(summary.medianSpearman)}</dd></div>
              <div><dt className="label">Median τ</dt><dd className="mt-1">{fmt(summary.medianKendall)}</dd></div>
              <div><dt className="label">Top-10 retained</dt><dd className="mt-1">{fmt(summary.medianTop10Retention, 1)} / 10</dd></div>
              <div><dt className="label">Top-20 retained</dt><dd className="mt-1">{fmt(summary.medianTop20Retention, 1)} / 20</dd></div>
              <div><dt className="label">Median |Δ rank|</dt><dd className="mt-1">{fmt(summary.medianRankDisplacement, 1)}</dd></div>
              <div><dt className="label">Max |Δ rank|</dt><dd className="mt-1">{fmt(summary.maxRankDisplacement, 0)}</dd></div>
            </dl>
          </article>
        ))}
      </div>

      <details className="mt-6 rounded-lg border border-[#1e314b] bg-[#09111f]">
        <summary className="cursor-pointer px-4 py-4 text-sm font-medium marker:text-cyan focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan">
          Explore individual runs <span className="ml-2 font-mono text-xs text-mute">{filteredRuns.length} shown / {runs.length} total</span>
        </summary>
        <div className="border-t border-[#1e314b] p-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Filter label="Perturbation family" value={familyFilter} onChange={setFamilyFilter} options={familyOptions.map((value) => [value, familyLabels[value] ?? value])} />
            <Filter label="Baseline mode" value={modeFilter} onChange={setModeFilter} options={(['spectral', 'image', 'multimodal'] as const).map((value) => [value, modeLabels[value]])} />
            <Filter label="Severity level" value={levelFilter} onChange={setLevelFilter} options={levelOptions.map((value) => [String(value), String(value)])} />
            <Filter label="Seed" value={seedFilter} onChange={setSeedFilter} options={seedOptions.map((value) => [String(value), String(value)])} />
          </div>

          {filteredRuns.length ? (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-[780px] w-full text-left text-xs">
                <caption className="sr-only">Individual Phase 5 controlled perturbation run metrics</caption>
                <thead>
                  <tr className="border-b border-[#29415d] text-mute">
                    <th scope="col" className="px-2 py-3">Family</th>
                    <th scope="col" className="px-2 py-3">Mode</th>
                    <th scope="col" className="px-2 py-3">Level</th>
                    <th scope="col" className="px-2 py-3">Seed</th>
                    <th scope="col" className="px-2 py-3">Spearman ρ</th>
                    <th scope="col" className="px-2 py-3">Top-10</th>
                    <th scope="col" className="px-2 py-3">Top-20</th>
                    <th scope="col" className="px-2 py-3">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRuns.map((run) => (
                    <tr key={runKey(run)} className="border-b border-[#182941]">
                      <td className="px-2 py-3">{familyLabels[run.scenario] ?? run.scenario}</td>
                      <td className="px-2 py-3">{modeLabels[run.mode]}</td>
                      <td className="px-2 py-3 font-mono">{run.level}</td>
                      <td className="px-2 py-3 font-mono">{run.seed}</td>
                      <td className="px-2 py-3">{fmt(run.spearman)}</td>
                      <td className="px-2 py-3">{run.top10_retention} / 10</td>
                      <td className="px-2 py-3">{run.top20_retention} / 20</td>
                      <td className="px-2 py-3">
                        <button
                          type="button"
                          aria-pressed={selectedRun != null && runKey(selectedRun) === runKey(run)}
                          onClick={() => setSelectedRun(run)}
                          className="rounded border border-[#365471] px-2 py-1 text-cyan hover:border-cyan focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 rounded-lg border border-dashed border-[#365471] p-5 text-sm text-mute">
              No recorded runs match these filters.
            </p>
          )}

          {selectedRun && filteredRuns.some((run) => runKey(run) === runKey(selectedRun)) && (
            <RunDetail run={selectedRun} />
          )}
        </div>
      </details>

      <p className="mt-5 border-t border-[#1e314b] pt-4 text-xs leading-5 text-mute">
        Interpretation boundary: every degraded run refits the model, imputation, and scaling. These records measure sensitivity to the listed perturbations only; stability is not scientific validation, physical significance, or a discovery probability.
      </p>
    </section>
  );
}

function ChartPanel({
  title,
  subtitle,
  data,
  dataKey,
  domain,
  color,
  formatter,
}: {
  title: string;
  subtitle: string;
  data: { family: string; scenario: string; medianSpearman: number | null; medianTop20: number | null }[];
  dataKey: 'medianSpearman' | 'medianTop20';
  domain: [number, number];
  color: string;
  formatter: (value: number | null) => string;
}) {
  return (
    <figure className="rounded-lg border border-[#1e314b] bg-[#09111f] p-4" aria-label={title}>
      <figcaption>
        <h3 className="font-medium">{title}</h3>
        <p className="mt-1 text-xs text-mute">{subtitle}</p>
      </figcaption>
      <div className="mt-4 h-[240px]" role="img" aria-label={`${title} by perturbation family`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid stroke="#1e314b" strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" domain={domain} tick={{ fill: '#91a0b8', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#365471' }} />
            <YAxis type="category" dataKey="family" width={118} tick={{ fill: '#c7d4e4', fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: 'rgba(131,214,210,.08)' }}
              contentStyle={{ background: '#09111f', border: '1px solid #365471', borderRadius: 8, color: '#e5edf7' }}
              labelStyle={{ color: '#e5edf7' }}
              formatter={(value) => [formatter(typeof value === 'number' ? value : null), title]}
              labelFormatter={(_, payload) => payload[0]?.payload?.scenario ? familyLabels[payload[0].payload.scenario] : ''}
            />
            <Bar dataKey={dataKey} fill={color} radius={[0, 4, 4, 0]} barSize={18} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="sr-only">
        {data.map((item) => (
          <li key={item.scenario}>{item.family}: {formatter(item[dataKey])}</li>
        ))}
      </ul>
    </figure>
  );
}

function Filter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="flex flex-col gap-1.5 text-xs text-mute">
      {label}
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-[#29415d] bg-[#080f1a] px-3 py-2 text-sm text-[#e5edf7] outline-none focus:border-cyan"
      >
        <option value="all">All</option>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>{optionLabel}</option>
        ))}
      </select>
    </label>
  );
}

function RunDetail({ run }: { run: RobustnessRun }) {
  return (
    <section aria-label="Selected run details" className="mt-4 rounded-lg border border-[#365471] bg-[#080f1a] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium">Selected run · {familyLabels[run.scenario] ?? run.scenario}</h3>
        <p className="font-mono text-xs text-mute">{modeLabels[run.mode]} · level {run.level} · seed {run.seed}</p>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3 lg:grid-cols-6">
        <div><dt className="label">Spearman ρ</dt><dd className="mt-1">{fmt(run.spearman)}</dd></div>
        <div><dt className="label">Kendall τ</dt><dd className="mt-1">{fmt(run.kendall)}</dd></div>
        <div><dt className="label">Top-10 overlap</dt><dd className="mt-1">{run.top10_retention} / 10</dd></div>
        <div><dt className="label">Top-20 overlap</dt><dd className="mt-1">{run.top20_retention} / 20</dd></div>
        <div><dt className="label">Median |Δ rank|</dt><dd className="mt-1">{fmt(run.median_abs_rank_displacement, 1)}</dd></div>
        <div><dt className="label">Max |Δ rank|</dt><dd className="mt-1">{fmt(run.max_abs_rank_displacement, 0)}</dd></div>
      </dl>
      <div className="mt-4 border-t border-[#1e314b] pt-3">
        <p className="label">New entries in the perturbed top 20</p>
        {run.new_top20_specids.length ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {run.new_top20_specids.map((specid) => (
              <li key={specid}>
                <Link
                  href={`/atlas?specid=${encodeURIComponent(specid)}`}
                  className="rounded-full border border-[#365471] px-2.5 py-1 font-mono text-xs text-cyan hover:border-cyan"
                >
                  {specid}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-mute">No new entries were recorded for this run.</p>
        )}
      </div>
    </section>
  );
}
