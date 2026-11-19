'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import SkyScene from '../observatory/SkyScene';
import { selectCandidates } from '../lib/selection';
import EvidenceDisplay from './EvidenceDisplay';
import RobustnessStudio from './RobustnessStudio';
import { useObservationSelection } from '../lib/use-observation-selection';
import type { Candidate, Dossier, Observation, RobustnessRun, SpectrumPayload } from '../lib/types';

type ResearchSummary = { audit: { source?: string }; [key: string]: unknown };
type Props = { observations: Observation[]; candidates: Candidate[]; robustness: RobustnessRun[]; research: ResearchSummary };

const fmt = (value: number | null | undefined, digits = 2) => value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits);

const chip = (value: string) => <span className="rounded-full border border-[#365471] bg-[#102136] px-3 py-1 text-xs text-cyan">{value}</span>;

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return <div className="card p-5"><p className="metric">{value}</p><p className="label mt-1">{label}</p><p className="mt-1 text-xs text-mute">{sub}</p></div>;
}

export default function ObservatoryClient({ observations, candidates, robustness, research }: Props) {
  const { specid, selectSpecid } = useObservationSelection();
  const selected = observations.find((item) => item.specid === specid) ?? observations[0] ?? null;
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [sort, setSort] = useState<'multimodal_rank' | 'spectral_rank' | 'image_rank'>('multimodal_rank');
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [spectrum, setSpectrum] = useState<SpectrumPayload | null>(null);
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const categories = useMemo(() => ['All', ...Array.from(new Set(candidates.map((item) => item.triage_category))).sort()], [candidates]);
  const filtered = useMemo(() => selectCandidates(candidates, query, category, sort), [candidates, query, category, sort]);

  useEffect(() => {
    if (!selected?.hasDossier) {
      setDossier(null);
      setSpectrum(null);
      setLoadState('ready');
      return;
    }
    let cancelled = false;
    setLoadState('loading');
    setDossier(null);
    setSpectrum(null);
    const detailRequest = fetch(`/api/candidates/${selected.specid}`, { cache: 'no-store' }).then((response) => {
      if (!response.ok) throw new Error('Dossier request failed');
      return response.json() as Promise<Dossier>;
    });
    const spectrumRequest = selected.hasSpectrumData
      ? fetch(`/api/candidates/${selected.specid}/spectrum`, { cache: 'no-store' }).then((response) => response.ok ? response.json() as Promise<SpectrumPayload> : null)
      : Promise.resolve(null);
    Promise.all([detailRequest, spectrumRequest]).then(([detail, spectralData]) => {
      if (cancelled) return;
      setDossier(detail);
      setSpectrum(spectralData);
      setLoadState('ready');
    }).catch(() => { if (!cancelled) setLoadState('error'); });
    return () => { cancelled = true; };
  }, [selected?.specid, selected?.hasDossier, selected?.hasSpectrumData]);

  const phase6Count = observations.filter((item) => item.hasDossier).length;
  const orderedCandidates = useMemo(
    () => [...candidates].sort((a, b) => a.multimodal_rank - b.multimodal_rank),
    [candidates],
  );
  const selectedCandidateIndex = selected
    ? orderedCandidates.findIndex((item) => item.specid === selected.specid)
    : -1;
  const previousCandidate = selectedCandidateIndex > 0 ? orderedCandidates[selectedCandidateIndex - 1] : null;
  const nextCandidate = selectedCandidateIndex >= 0 ? orderedCandidates[selectedCandidateIndex + 1] ?? null : null;

  return <main className="min-h-screen bg-[#070b14] text-[#e5edf7]">
    <header className="border-b border-[#1e314b] bg-[#09111f]/85"><div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8"><div><Link href="/" className="label text-cyan">LIMEN / research observatory</Link><h1 className="mt-1 text-2xl font-semibold">The Observatory</h1></div><nav aria-label="Research destinations" className="flex items-center gap-2"><Link href="/atlas" className="rounded-full border border-[#365471] px-4 py-2 text-sm hover:border-cyan">Galaxy Atlas</Link><Link href="/observatory#research" className="rounded-full border border-[#365471] px-4 py-2 text-sm hover:border-cyan">Research record</Link></nav></div></header>
    <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8">
      <section className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]"><div className="card p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="label">The 200-object pilot</p><h2 className="mt-1 text-xl">Anomaly candidates, in context</h2><p className="mt-2 max-w-xl text-sm leading-6 text-mute">All 200 joined Phase 2 observations appear in their sky positions. Muted points have no Phase 6 dossier; select any point to carry its identity into the evidence panel.</p></div>{chip(`${phase6Count} investigated`)}</div><div className="mt-5"><SkyScene observations={observations} selectedId={selected?.specid ?? null} onPick={selectSpecid}/></div><div className="mt-4 flex flex-wrap gap-4 text-xs text-mute"><span><i className="mr-2 inline-block size-2 rounded-full bg-[#718199]"/>Catalog only</span><span><i className="mr-2 inline-block size-2 rounded-full bg-[#83d6d2]"/>Phase 6 spectral evidence</span><span><i className="mr-2 inline-block size-2 rounded-full bg-[#f2c977]"/>Multimodal evidence</span><span>Drag to rotate · scroll to zoom · select a point</span></div></div>
        <div className="grid content-start gap-4 sm:grid-cols-2"><Metric label="Observations" value="200" sub="Phase 2 cached multimodal pilot"/><Metric label="Investigated" value={String(phase6Count)} sub="Phase 6 dossiers · not classifications"/><Metric label="Spectral rank" value={selected ? `#${selected.spectral_rank ?? '—'}` : '—'} sub={selected ? `score ${fmt(selected.spectral_score, 3)}` : 'Select an observation'}/><Metric label="Image rank" value={selected ? `#${selected.image_rank ?? '—'}` : '—'} sub={selected ? `score ${fmt(selected.image_score, 3)}` : 'Select an observation'}/><div className="card p-5 sm:col-span-2"><p className="label">Identity held across views</p><h2 className="mt-1 font-mono text-lg">{selected?.specid ?? 'No observation selected'}</h2><p className="mt-2 text-sm text-mute">The selected specid is in the URL. Use the Atlas to search, sort and filter the complete catalog.</p><Link href={selected ? `/atlas?specid=${encodeURIComponent(selected.specid)}` : '/atlas'} className="mt-4 inline-flex rounded-full border border-[#365471] px-4 py-2 text-sm text-cyan hover:border-cyan">Open in Galaxy Atlas →</Link></div></div></section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[.85fr_1.15fr]"><div id="candidate-explorer" className="card overflow-hidden"><div className="border-b border-[#1e314b] p-4"><div className="flex items-center justify-between gap-2"><p className="label">Candidate explorer / {filtered.length} of {candidates.length}</p><Link href={selected ? `/atlas?specid=${encodeURIComponent(selected.specid)}` : '/atlas'} className="text-xs text-cyan underline-offset-4 hover:underline">Full catalog →</Link></div><div className="mt-3 grid gap-2 sm:grid-cols-2"><input aria-label="Search candidates" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search specid or targetid" className="rounded-lg border border-[#29415d] bg-[#09111f] px-3 py-2 text-sm outline-none focus:border-cyan"/><select aria-label="Filter triage category" value={category} onChange={(event) => setCategory(event.target.value)} className="rounded-lg border border-[#29415d] bg-[#09111f] px-3 py-2 text-sm">{categories.map((value) => <option key={value}>{value}</option>)}</select><select aria-label="Sort candidates" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="rounded-lg border border-[#29415d] bg-[#09111f] px-3 py-2 text-sm sm:col-span-2"><option value="multimodal_rank">Sort: original multimodal rank</option><option value="spectral_rank">Sort: original spectral rank</option><option value="image_rank">Sort: original image rank</option></select></div></div><div className="scroll max-h-[630px] overflow-y-auto">{filtered.map((item) => <button key={item.specid} type="button" onClick={() => selectSpecid(item.specid)} aria-pressed={selected?.specid === item.specid} className={`w-full border-b border-[#182941] p-4 text-left transition hover:bg-[#101e32] ${selected?.specid === item.specid ? 'bg-[#122640]' : ''}`}><div className="flex justify-between gap-3"><div><div className="font-mono text-sm">{item.specid}</div><div className="mt-1 text-xs text-mute">RA {item.ra_deg.toFixed(3)}° · Dec {item.dec_deg.toFixed(3)}° · z {fmt(item.redshift, 3)}</div></div><span className="text-right text-xs text-cyan">M {item.multimodal_rank}<br/>S {item.spectral_rank} · I {item.image_rank}</span></div><p className="mt-2 text-xs text-mute">{item.triage_category}</p></button>)}</div></div>
        <section id="evidence" aria-label="Evidence laboratory" tabIndex={-1}><EvidenceDisplay dossier={dossier} spectrum={spectrum} selected={selected} loadState={loadState} previousCandidate={previousCandidate} nextCandidate={nextCandidate} onSelectSpecid={selectSpecid}/></section></section>

      <section className="mt-6 grid gap-6"><RobustnessStudio runs={robustness}/></section>

      <section className="mt-6"><div id="research" className="card p-5"><p className="label">Research record</p><h2 className="mt-1 text-xl">Methods & limits</h2><ul className="mt-4 flex flex-col gap-3 text-sm text-mute"><li>Phase 2: all 200 cached spectra and images read successfully; 3×64×64 grz cutouts.</li><li>Phase 3: fixed-seed Isolation Forest spectral, image, and equalized multimodal baselines.</li><li>Phase 4: mask-aware residual context and individual DESI ZWARN bit decoding.</li><li>Phase 6: transparent categories are workflow labels, not astronomy classifications.</li><li>Legacy Survey imagery is cross-survey consistency evidence, not independent confirmation.</li><li>Source record: {String(research.audit.source ?? 'DESI DR1 pilot')}; reported catalog rows: 200.</li></ul></div></section>
    </div>
  </main>;
}
