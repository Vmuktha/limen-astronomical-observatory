'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { Observation } from '../lib/types';
import { useObservationSelection } from '../lib/use-observation-selection';

const PAGE_SIZE = 48;
const modalities = [
  { value: 'all', label: 'All modalities' },
  { value: 'spectral', label: 'Spectral top 20' },
  { value: 'image', label: 'Image top 20' },
  { value: 'multimodal', label: 'Multimodal top 20' },
] as const;
const numberLabel = (value: number | null, digits = 3) => value == null ? '—' : value.toFixed(digits);
const rankLabel = (value: number | null) => value == null ? '—' : `#${value}`;

type Modality = (typeof modalities)[number]['value'];
type SortKey = 'spectral_rank' | 'image_rank' | 'multimodal_rank';

export default function AtlasExplorer({ observations }: { observations: Observation[] }) {
  const { specid, selectSpecid } = useObservationSelection();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All categories');
  const [modality, setModality] = useState<Modality>('all');
  const [sort, setSort] = useState<SortKey>('multimodal_rank');
  const [page, setPage] = useState(0);

  const categories = useMemo(() => ['All categories', 'Not investigated', ...Array.from(new Set(observations.flatMap((item) => item.triage_category ? [item.triage_category] : []))).sort()], [observations]);
  const relationships = useMemo(() => ['All relationships', 'Not recorded', ...Array.from(new Set(observations.flatMap((item) => item.modality_relationship ? [item.modality_relationship] : []))).sort()], [observations]);
  const [relationship, setRelationship] = useState('All relationships');
  const filtered = useMemo(() => observations
    .filter((item) => {
      const matchesQuery = `${item.specid} ${item.targetid}`.includes(query.trim());
      const matchesCategory = category === 'All categories' || (category === 'Not investigated' ? !item.hasDossier : item.triage_category === category);
      const matchesRelationship = relationship === 'All relationships' || (relationship === 'Not recorded' ? !item.modality_relationship : item.modality_relationship === relationship);
      const rank = modality === 'all' ? true : item[`${modality}_rank` as SortKey] != null && item[`${modality}_rank` as SortKey]! <= 20;
      return matchesQuery && matchesCategory && matchesRelationship && rank;
    })
    .sort((a, b) => (a[sort] ?? Number.MAX_SAFE_INTEGER) - (b[sort] ?? Number.MAX_SAFE_INTEGER)), [observations, query, category, relationship, modality, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <main className="min-h-screen bg-[#070b14] text-[#e5edf7]">
      <header className="border-b border-white/[0.07] bg-[#09111f]/80">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-5 px-5 py-6 sm:px-8">
          <div>
            <Link href="/" className="text-[11px] uppercase tracking-[0.28em] text-cyan">LIMEN / survey instruments</Link>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Galaxy Atlas</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#91a4bd]">A catalog of 200 DESI DR1 observations, joined to their Phase 3 anomaly scores and Phase 6 investigation status.</p>
          </div>
          <Link href={specid ? `/observatory?specid=${encodeURIComponent(specid)}#evidence` : '/observatory'} className="rounded-full border border-[#365471] px-4 py-2 text-sm text-[#d9e9f8] transition hover:border-cyan hover:text-white">Open Observatory</Link>
        </div>
      </header>

      <div className="mx-auto max-w-[1500px] px-5 py-6 sm:px-8">
        <section aria-label="Atlas filters" className="rounded-2xl border border-white/[0.09] bg-[#0c1523]/90 p-4 shadow-[0_20px_80px_rgba(0,0,0,.2)] sm:p-5">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1.35fr_1fr_1.1fr_1fr_1fr]">
            <label className="flex flex-col gap-2 text-[11px] uppercase tracking-[0.18em] text-[#91a4bd]">Search observations
              <input aria-label="Search by specid or targetid" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="specid or targetid" className="h-11 rounded-lg border border-[#263b53] bg-[#080f1a] px-3 font-mono text-sm normal-case tracking-normal text-[#e5edf7] outline-none placeholder:text-[#62758e] focus:border-cyan" />
            </label>
            <label className="flex flex-col gap-2 text-[11px] uppercase tracking-[0.18em] text-[#91a4bd]">Triage category
              <select aria-label="Filter by triage category" value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }} className="h-11 rounded-lg border border-[#263b53] bg-[#080f1a] px-3 text-sm normal-case tracking-normal text-[#e5edf7] outline-none focus:border-cyan">{categories.map((value) => <option key={value}>{value}</option>)}</select>
            </label>
            <label className="flex flex-col gap-2 text-[11px] uppercase tracking-[0.18em] text-[#91a4bd]">Modality relationship
              <select aria-label="Filter by modality relationship" value={relationship} onChange={(event) => { setRelationship(event.target.value); setPage(0); }} className="h-11 rounded-lg border border-[#263b53] bg-[#080f1a] px-3 text-sm normal-case tracking-normal text-[#e5edf7] outline-none focus:border-cyan">{relationships.map((value) => <option key={value}>{value}</option>)}</select>
            </label>
            <label className="flex flex-col gap-2 text-[11px] uppercase tracking-[0.18em] text-[#91a4bd]">Anomaly modality
              <select aria-label="Filter by anomaly modality" value={modality} onChange={(event) => { setModality(event.target.value as Modality); setPage(0); }} className="h-11 rounded-lg border border-[#263b53] bg-[#080f1a] px-3 text-sm normal-case tracking-normal text-[#e5edf7] outline-none focus:border-cyan">{modalities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
            </label>
            <label className="flex flex-col gap-2 text-[11px] uppercase tracking-[0.18em] text-[#91a4bd]">Rank order
              <select aria-label="Sort by anomaly rank" value={sort} onChange={(event) => setSort(event.target.value as SortKey)} className="h-11 rounded-lg border border-[#263b53] bg-[#080f1a] px-3 text-sm normal-case tracking-normal text-[#e5edf7] outline-none focus:border-cyan">
                <option value="multimodal_rank">Multimodal rank</option><option value="spectral_rank">Spectral rank</option><option value="image_rank">Image rank</option>
              </select>
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4 text-xs text-[#91a4bd]"><span><strong className="font-mono text-[#e5edf7]">{filtered.length}</strong> of 200 observations · {observations.filter((item) => item.hasDossier).length} investigated in Phase 6</span><span>Ranks are relative within the pilot; not probabilities or discovery claims.</span></div>
        </section>

        {visible.length ? <section aria-label="Observation results" className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((item) => <article key={item.specid} className={`group overflow-hidden rounded-2xl border bg-[#0b1421] transition ${specid === item.specid ? 'border-cyan/70 shadow-[0_0_0_1px_rgba(131,214,210,.16)]' : 'border-white/[0.08] hover:border-white/[0.18]'}`}>
            <button type="button" onClick={() => selectSpecid(item.specid)} aria-pressed={specid === item.specid} aria-label={`Select observation ${item.specid}`} className="block w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-cyan">
              <div className="relative aspect-square overflow-hidden bg-[radial-gradient(ellipse_at_center,rgba(42,77,107,.28),rgba(5,10,18,.92)_72%)]">
                {item.hasImagePreview ? <img src={`/api/candidates/${item.specid}/image`} alt={`Existing Phase 4 composite figure showing DESI spectrum and Legacy Survey image evidence for observation ${item.specid}`} loading="lazy" className="size-full object-contain transition duration-500 group-hover:scale-[1.025]" /> : <div className="flex size-full flex-col items-center justify-center gap-2 px-6 text-center"><span className="font-mono text-2xl text-[#667d98]">{item.specid}</span><span className="rounded-full border border-[#52647a]/50 bg-[#0b1421]/80 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-[#a9b8ca]">Image unavailable</span><span className="text-xs text-[#73869e]">No browser preview exported for this observation</span></div>}
                <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-[#070b14]/95 via-[#070b14]/50 to-transparent px-4 pb-3 pt-10"><span className="font-mono text-sm text-white">{item.specid}</span><span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] ${item.hasDossier ? 'border-cyan/40 bg-cyan/10 text-cyan' : 'border-white/15 bg-black/20 text-[#b0bdcb]'}`}>{item.hasDossier ? 'Phase 6 dossier' : 'Not investigated'}</span></div>
              </div>
              <div className="p-4">
                <div className="flex items-start justify-between gap-3"><div><p className="text-[10px] uppercase tracking-[0.18em] text-[#73869e]">Target {item.targetid}</p><p className="mt-1 font-mono text-xs text-[#b7c7d9]">RA {numberLabel(item.ra_deg)}° <span className="text-[#61758e]">/</span> Dec {numberLabel(item.dec_deg)}°</p></div><span className="text-right text-[10px] text-[#73869e]">z<br/><span className="font-mono text-xs text-[#d6e2ef]">{numberLabel(item.redshift)}</span></span></div>
                <div className="mt-4 grid grid-cols-3 gap-2 border-t border-white/[0.07] pt-3 text-[10px] uppercase tracking-[0.1em] text-[#7589a1]"><span>Spectral <strong className="mt-1 block font-mono text-sm tracking-normal text-[#d9e7f4]">{rankLabel(item.spectral_rank)}</strong></span><span>Image <strong className="mt-1 block font-mono text-sm tracking-normal text-[#d9e7f4]">{rankLabel(item.image_rank)}</strong></span><span>Combined <strong className="mt-1 block font-mono text-sm tracking-normal text-cyan">{rankLabel(item.multimodal_rank)}</strong></span></div>
                <p className="mt-3 min-h-5 text-xs text-[#91a4bd]">{item.triage_category ?? 'No Phase 6 triage category'}</p>
              </div>
            </button>
            <div className="flex items-center justify-between border-t border-white/[0.07] px-4 py-3"><span className="text-[10px] uppercase tracking-[0.16em] text-[#687d96]">Scores: S {numberLabel(item.spectral_score)} · I {numberLabel(item.image_score)} · M {numberLabel(item.multimodal_score)}</span><Link href={`/observatory?specid=${encodeURIComponent(item.specid)}#evidence`} className="text-xs text-cyan underline-offset-4 hover:underline">Evidence →</Link></div>
          </article>)}
        </section> : <div className="mt-5 rounded-2xl border border-dashed border-[#314760] px-6 py-16 text-center"><p className="text-lg">No observations match these filters.</p><p className="mt-2 text-sm text-[#91a4bd]">Adjust the query, category or anomaly modality.</p></div>}

        <nav aria-label="Atlas pages" className="mt-6 flex items-center justify-between rounded-xl border border-white/[0.08] bg-[#0b1421] px-4 py-3 text-sm"><span className="text-[#91a4bd]">Page {page + 1} of {pageCount}</span><div className="flex gap-2"><button type="button" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))} className="rounded-md border border-[#263b53] px-3 py-2 disabled:cursor-not-allowed disabled:opacity-40">Previous</button><button type="button" disabled={page >= pageCount - 1} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))} className="rounded-md border border-[#263b53] px-3 py-2 disabled:cursor-not-allowed disabled:opacity-40">Next</button></div></nav>
      </div>
    </main>
  );
}
