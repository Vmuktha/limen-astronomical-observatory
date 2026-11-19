'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import SpectrumCharts from './SpectrumCharts';
import type { Candidate, CandidateRobustness, Dossier, Observation, SpectrumPayload } from '../lib/types';

type Props = {
  dossier: Dossier | null;
  spectrum: SpectrumPayload | null;
  selected: Observation | null;
  loadState: 'idle' | 'loading' | 'ready' | 'error';
  previousCandidate: Candidate | null;
  nextCandidate: Candidate | null;
  onSelectSpecid: (specid: string | null) => void;
};

const fmt = (value: number | null | undefined, digits = 2) =>
  value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits);

function numericValue(record: Record<string, unknown> | undefined, key: string) {
  const value = record?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="card p-4">
      <p className="metric">{value}</p>
      <p className="label mt-1">{label}</p>
      <p className="mt-1 text-xs text-mute">{sub}</p>
    </div>
  );
}

function EvidenceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-[#09111f] p-2.5">
      <dt className="label">{label}</dt>
      <dd className="mt-1 font-mono text-[#d8e4f2]">{value}</dd>
    </div>
  );
}

function Phase4Figure({ specid, available }: { specid: string; available: boolean }) {
  const [failed, setFailed] = useState(false);

  if (!available || failed) {
    return (
      <div role="status" className="flex min-h-[280px] flex-col items-center justify-center rounded-lg border border-dashed border-[#365471] bg-[#080f1a] px-6 text-center">
        <p className="label">Phase 4 evidence figure</p>
        <p className="mt-3 text-sm text-mute">
          {failed ? 'The real evidence image endpoint could not load this figure.' : 'No exported Phase 4 figure is recorded for this observation.'}
        </p>
      </div>
    );
  }

  return (
    <img
      src={`/api/candidates/${specid}/image`}
      alt={`Phase 4 evidence composite for ${specid}, containing DESI spectral diagnostics and Legacy Survey grz imaging`}
      className="max-h-[520px] w-full rounded-lg border border-[#29415d] bg-[#080f1a] object-contain"
      onError={() => setFailed(true)}
    />
  );
}

export default function EvidenceDisplay({
  dossier,
  spectrum,
  selected,
  loadState,
  previousCandidate,
  nextCandidate,
  onSelectSpecid,
}: Props) {
  if (!selected) {
    return (
      <div className="card p-6">
        <p className="text-mute">Select an observation from the catalog to view its evidence.</p>
      </div>
    );
  }

  if (!selected.hasDossier) {
    return (
      <div className="card min-h-[440px] p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="label">Evidence laboratory / catalog only</p>
            <h2 className="mt-2 font-mono text-2xl">{selected.specid}</h2>
          </div>
          <span className="rounded-full border border-[#52647a] px-3 py-1 text-xs text-[#c0ccda]">No Phase 6 dossier</span>
        </div>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-mute">
          This observation is part of the 200-object catalog, but it is not one of the 39 objects with a Phase 6 dossier. Only its recorded catalog identity and Phase 3 baseline ranks are shown here; no candidate interpretation or evidence diagnostics are inferred.
        </p>
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <MetricCard label="Spectral rank" value={selected.spectral_rank == null ? '—' : `#${selected.spectral_rank}`} sub={`relative score ${fmt(selected.spectral_score, 3)}`} />
          <MetricCard label="Image rank" value={selected.image_rank == null ? '—' : `#${selected.image_rank}`} sub={`relative score ${fmt(selected.image_score, 3)}`} />
          <MetricCard label="Multimodal rank" value={selected.multimodal_rank == null ? '—' : `#${selected.multimodal_rank}`} sub={`relative score ${fmt(selected.multimodal_score, 3)}`} />
        </div>
        <div className="mt-5 flex flex-wrap gap-4 text-sm">
          <Link href="#candidate-explorer" className="text-cyan underline-offset-4 hover:underline">Return to candidate explorer</Link>
          <Link href={`/atlas?specid=${encodeURIComponent(selected.specid)}`} className="text-cyan underline-offset-4 hover:underline">Open in Galaxy Atlas</Link>
        </div>
      </div>
    );
  }

  const candidate = dossier?.candidate;
  const phase4 = dossier?.phase4 ?? null;
  const spectralQuality = phase4?.spectral_quality;
  const imageEvidence = phase4?.image_evidence;
  const imageQuality = imageEvidence?.quality_and_proxy_metrics;
  const residuals = phase4?.model_discrepancy;
  const warning = phase4?.redshift_warning ?? candidate?.redshift_warning;
  const flags = warning?.flags ?? [];
  const wavelengthStart = numericValue(spectralQuality, 'wavelength_min_angstrom');
  const wavelengthEnd = numericValue(spectralQuality, 'wavelength_max_angstrom');
  const wavelengthRange = wavelengthStart == null || wavelengthEnd == null
    ? '—'
    : `${Math.round(wavelengthStart)}–${Math.round(wavelengthEnd)} Å`;
  const robustnessData = dossier?.evidence_dimensions.robustness ?? {};
  const robustness = Object.entries(robustnessData).filter(
    (entry): entry is [string, CandidateRobustness] => typeof entry[1] === 'object' && entry[1] !== null,
  );
  const missingModalityBehavior = typeof robustnessData.missing_modality_behavior === 'string'
    ? robustnessData.missing_modality_behavior
    : null;
  const phase6Discrepancy = dossier?.evidence_dimensions.model_discrepancy;
  const discrepancyRegions = Array.isArray(residuals?.discrepancy_regions)
    ? residuals.discrepancy_regions.filter((value): value is Record<string, unknown> => typeof value === 'object' && value !== null)
    : [];

  return (
    <div className="card min-h-[440px] p-5 sm:p-6">
      <AnimatePresence mode="wait">
        <motion.div
          key={selected.specid}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
        >
          <header className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="label">Evidence laboratory / Phase 6 dossier</p>
              <h2 className="mt-1 font-mono text-xl" aria-live="polite">{selected.specid}</h2>
              <p className="mt-1 text-sm text-mute">{dossier?.triage.category ?? selected.triage_category}</p>
            </div>
            <span className="rounded-full border border-[#365471] bg-[#102136] px-3 py-1 text-xs text-cyan">
              {candidate ? `ZWARN ${warning?.value ?? '—'}` : loadState === 'error' ? 'Dossier unavailable' : 'Loading dossier'}
            </span>
          </header>

          <nav aria-label="Candidate navigation" className="mt-4 flex flex-wrap items-center justify-between gap-3 border-y border-[#1e314b] py-3">
            <button
              type="button"
              disabled={!previousCandidate}
              onClick={() => previousCandidate && onSelectSpecid(previousCandidate.specid)}
              className="rounded-full border border-[#365471] px-3 py-2 text-xs text-cyan transition hover:border-cyan disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Previous investigated candidate
            </button>
            <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
              <Link href="#candidate-explorer" className="text-mute underline-offset-4 hover:text-cyan hover:underline">Back to candidate explorer</Link>
              <Link href={`/atlas?specid=${encodeURIComponent(selected.specid)}`} className="text-mute underline-offset-4 hover:text-cyan hover:underline">Open in Galaxy Atlas</Link>
            </div>
            <button
              type="button"
              disabled={!nextCandidate}
              onClick={() => nextCandidate && onSelectSpecid(nextCandidate.specid)}
              className="rounded-full border border-[#365471] px-3 py-2 text-xs text-cyan transition hover:border-cyan disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next investigated candidate →
            </button>
          </nav>

          {loadState === 'loading' && <p role="status" className="mt-3 text-xs text-mute">Loading Phase 4 diagnostics and Phase 6 interpretation…</p>}
          {loadState === 'error' && <p role="alert" className="mt-3 rounded-lg border border-[#7d5d38] bg-[#241c12] p-3 text-xs leading-5 text-[#f0d2a1]">The dossier request failed. The catalog identity and Phase 4 figure remain available, but dossier diagnostics are not being inferred.</p>}

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <MetricCard label="Spectral baseline" value={selected.spectral_rank == null ? '—' : `#${selected.spectral_rank}`} sub={`relative score ${fmt(selected.spectral_score, 3)}`} />
            <MetricCard label="Image baseline" value={selected.image_rank == null ? '—' : `#${selected.image_rank}`} sub={`relative score ${fmt(selected.image_score, 3)}`} />
            <MetricCard label="Multimodal baseline" value={selected.multimodal_rank == null ? '—' : `#${selected.multimodal_rank}`} sub={`relative score ${fmt(selected.multimodal_score, 3)}`} />
          </div>

          <section aria-labelledby="observed-evidence-title" className="mt-6">
            <p className="label">Observed evidence / Phase 4</p>
            <h3 id="observed-evidence-title" className="mt-1 text-lg font-medium">Composite figure and source measurements</h3>
            <p className="mt-1 text-xs text-mute">The figure is served by the existing candidate image endpoint. Values below come from the candidate&apos;s Phase 4 evidence dossier.</p>
            <div className="mt-4 grid gap-5 xl:grid-cols-[1.35fr_.9fr]">
              <div>
                {spectrum ? (
                  <SpectrumCharts spectrum={spectrum} />
                ) : (
                  <>
                    <Phase4Figure key={selected.specid} specid={selected.specid} available={selected.hasImagePreview} />
                    <p className="mt-2 text-xs leading-5 text-mute">
                      {selected.hasSpectrumData
                        ? 'Individual spectrum arrays are unavailable for this request; the Phase 4 composite remains the source figure.'
                        : 'Individual spectrum arrays are unavailable in this environment; no chart is fabricated. The existing Phase 4 composite remains the evidence view.'}
                    </p>
                  </>
                )}
              </div>

              <div className="flex flex-col gap-4">
                <section aria-labelledby="spectral-diagnostics-title">
                  <h4 id="spectral-diagnostics-title" className="label mb-2">Spectral diagnostics</h4>
                  {phase4 ? (
                    <dl className="grid grid-cols-2 gap-2 text-xs">
                      <EvidenceMetric label="Samples" value={fmt(numericValue(spectralQuality, 'samples'), 0)} />
                      <EvidenceMetric label="Valid pixels" value={fmt(numericValue(spectralQuality, 'valid_pixel_fraction'), 3)} />
                      <EvidenceMetric label="S/N median" value={fmt(numericValue(spectralQuality, 'snr_median'), 2)} />
                      <EvidenceMetric label="S/N |p90|" value={fmt(numericValue(spectralQuality, 'snr_abs_p90'), 2)} />
                      <EvidenceMetric label="Masked fraction" value={fmt(numericValue(spectralQuality, 'mask_nonzero_fraction'), 3)} />
                      <EvidenceMetric label="Wavelength range" value={wavelengthRange} />
                    </dl>
                  ) : <p className="text-xs leading-5 text-mute">Phase 4 diagnostic dossier is unavailable; measurements are not inferred from the Phase 6 summary.</p>}
                </section>

                <section aria-labelledby="image-diagnostics-title">
                  <h4 id="image-diagnostics-title" className="label mb-2">Image diagnostics</h4>
                  {imageQuality ? (
                    <dl className="grid grid-cols-2 gap-2 text-xs">
                      <EvidenceMetric label="Invalid fraction" value={fmt(numericValue(imageQuality, 'image_invalid_fraction'), 3)} />
                      <EvidenceMetric label="Finite fraction" value={fmt(numericValue(imageQuality, 'image_finite_fraction'), 3)} />
                      <EvidenceMetric label="S/N proxy median" value={fmt(numericValue(imageQuality, 'image_snr_proxy_median'), 2)} />
                      <EvidenceMetric label="Cutout dimensions" value={`${fmt(numericValue(imageQuality, 'image_height_px'), 0)} × ${fmt(numericValue(imageQuality, 'image_width_px'), 0)} px`} />
                    </dl>
                  ) : <p className="text-xs leading-5 text-mute">Image diagnostics are unavailable in the Phase 4 dossier.</p>}
                  {imageEvidence && Object.keys(imageEvidence.per_band_statistics).length > 0 && (
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full min-w-[340px] text-left text-[11px]">
                        <caption className="sr-only">Phase 4 image statistics by grz band</caption>
                        <thead><tr className="border-b border-[#29415d] text-mute"><th scope="col" className="py-2 pr-2">Band</th><th scope="col" className="py-2 pr-2">Median</th><th scope="col" className="py-2 pr-2">MAD</th><th scope="col" className="py-2">p05–p95</th></tr></thead>
                        <tbody>{Object.entries(imageEvidence.per_band_statistics).map(([band, stats]) => (
                          <tr key={band} className="border-b border-[#182941]">
                            <th scope="row" className="py-2 pr-2 font-mono uppercase">{band}</th>
                            <td className="py-2 pr-2 font-mono">{fmt(numericValue(stats, 'median'), 4)}</td>
                            <td className="py-2 pr-2 font-mono">{fmt(numericValue(stats, 'mad'), 4)}</td>
                            <td className="py-2 font-mono">{fmt(numericValue(stats, 'p05'), 3)}–{fmt(numericValue(stats, 'p95'), 3)}</td>
                          </tr>
                        ))}</tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section aria-labelledby="redshift-warning-title" className="rounded-lg border border-[#1e314b] bg-[#09111f] p-3">
                  <h4 id="redshift-warning-title" className="label">Redshift and quality warnings</h4>
                  <p className="mt-2 font-mono text-sm">z = {fmt(phase4?.redshift ?? selected.redshift, 5)}</p>
                  <p className="mt-1 text-xs text-mute">ZWARN value: {warning?.value ?? '—'}</p>
                  {flags.length ? (
                    <ul className="mt-2 flex flex-col gap-2 text-xs leading-5 text-mute">
                      {flags.map((flag) => <li key={flag.name}><strong className="text-[#f2c977]">{flag.name}</strong> — {flag.description}</li>)}
                    </ul>
                  ) : (
                    <p className="mt-1 text-xs text-mute">{warning?.value === 0 ? 'No ZWARN bits are set in the recorded dossier.' : 'No decoded ZWARN flag descriptions are recorded.'}</p>
                  )}
                </section>
              </div>
            </div>

            {residuals && discrepancyRegions.length > 0 && (
              <div className="mt-4 rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
                <h4 className="label">Recorded residual discrepancy regions</h4>
                <ul className="mt-2 flex flex-col gap-2 text-xs text-mute">
                  {discrepancyRegions.map((region, index) => (
                    <li key={index}>
                      {fmt(numericValue(region, 'wavelength_start_angstrom'), 1)}–{fmt(numericValue(region, 'wavelength_end_angstrom'), 1)} Å · {fmt(numericValue(region, 'pixels'), 0)} pixel(s) · max |standardized residual| {fmt(numericValue(region, 'max_abs_standardized_residual'), 2)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section aria-labelledby="diagnostic-results-title" className="mt-6 border-t border-[#1e314b] pt-5">
            <p className="label">Diagnostic results / Phase 6</p>
            <h3 id="diagnostic-results-title" className="mt-1 text-lg font-medium">Triage and sensitivity context</h3>
            <div className="mt-3 grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
                <p className="label">Workflow category</p>
                <p className="mt-2 text-sm font-medium text-cyan">{dossier?.triage.category ?? selected.triage_category ?? 'Loading Phase 6 dossier'}</p>
                <p className="mt-1 text-xs leading-5 text-mute">This is a triage label, not an astrophysical classification or discovery claim.</p>
                {dossier?.triage.reasons?.length ? (
                  <ul className="mt-3 flex flex-col gap-2 text-xs leading-5 text-mute">
                    {dossier.triage.reasons.map((reason) => <li key={reason}>• {reason}</li>)}
                  </ul>
                ) : null}
              </div>
              <div className="rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
                <p className="label">Cross-modal relationship</p>
                <p className="mt-2 text-sm text-[#dce7f4]">{candidate?.modality_relationship ?? selected.modality_relationship ?? '—'}</p>
                <p className="mt-1 text-xs leading-5 text-mute">Scores are relative Phase 3 baseline rankings, not probabilities.</p>
              </div>
            </div>

            <section aria-labelledby="phase6-discrepancy-title" className="mt-4 rounded-lg border border-[#1e314b] bg-[#09111f] p-4">
              <h4 id="phase6-discrepancy-title" className="label">Phase 6 residual and discrepancy context</h4>
              {phase6Discrepancy ? (
                <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                  <EvidenceMetric label="Valid residual pixels" value={fmt(numericValue(phase6Discrepancy, 'residual_valid_pixels'), 0)} />
                  <EvidenceMetric label="Valid residual fraction" value={fmt(numericValue(phase6Discrepancy, 'residual_valid_fraction'), 3)} />
                  <EvidenceMetric label="Residual RMS" value={fmt(numericValue(phase6Discrepancy, 'residual_rms'), 3)} />
                  <EvidenceMetric label="Standardized |residual| p95" value={fmt(numericValue(phase6Discrepancy, 'standardized_residual_abs_p95'), 3)} />
                  <EvidenceMetric label="Standardized |residual| p99" value={fmt(numericValue(phase6Discrepancy, 'standardized_residual_abs_p99'), 3)} />
                  <EvidenceMetric label="High-residual pixels" value={fmt(numericValue(phase6Discrepancy, 'high_standardized_residual_pixel_count'), 0)} />
                </dl>
              ) : (
                <p className="mt-2 text-xs leading-5 text-mute">Phase 6 discrepancy diagnostics are unavailable in this dossier.</p>
              )}
              <p className="mt-3 text-xs leading-5 text-mute">Residual diagnostics describe model discrepancy in the recorded spectrum; they do not establish physical-model failure.</p>
            </section>

            <div className="mt-4">
              <p className="label mb-2">Candidate-specific robustness evidence</p>
              {robustness.length ? (
                <div className="grid gap-3 sm:grid-cols-3">
                  {robustness.map(([name, result]) => (
                    <div key={name} className="rounded-lg border border-[#1e314b] bg-[#09111f] p-3">
                      <p className="label">{name} · {result.availability}</p>
                      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
                        <EvidenceMetric label="Runs" value={fmt(result.runs ?? null, 0)} />
                        <EvidenceMetric label="Median |Δ rank|" value={fmt(result.median_absolute_rank_displacement ?? null, 1)} />
                        <EvidenceMetric label="Max |Δ rank|" value={fmt(result.max_absolute_rank_displacement ?? null, 0)} />
                        <EvidenceMetric label="Top-20 retention fraction" value={fmt(result.top20_retention_fraction ?? null, 2)} />
                      </dl>
                    </div>
                  ))}
                </div>
              ) : <p className="text-xs text-mute">No candidate-level robustness summary is recorded.</p>}
              {missingModalityBehavior && <p className="mt-3 text-xs leading-5 text-mute">{missingModalityBehavior}</p>}
            </div>
          </section>

          <section aria-labelledby="interpretation-title" className="mt-6 rounded-lg border border-[#365471] bg-[#080f1a] p-4">
            <p className="label">Interpretation / uncertainty</p>
            <h3 id="interpretation-title" className="mt-1 text-base font-medium">Interpretation boundary</h3>
            <p className="mt-2 text-sm leading-6 text-mute">
              {dossier?.triage.interpretation_boundary ?? (loadState === 'error' ? 'The Phase 6 interpretation could not be loaded.' : 'Loading Phase 6 interpretation…')}
            </p>
            {dossier?.triage.remaining_uncertainties?.length ? (
              <div className="mt-4">
                <p className="label">Remaining uncertainties</p>
                <ul className="mt-2 flex flex-col gap-2 text-xs leading-5 text-mute">
                  {dossier.triage.remaining_uncertainties.map((item) => <li key={item}>• {item}</li>)}
                </ul>
              </div>
            ) : null}
            {candidate?.alternative_explanations?.length ? (
              <div className="mt-4">
                <p className="label">Recorded alternative explanations</p>
                <ul className="mt-2 flex flex-col gap-2 text-xs leading-5 text-mute">
                  {candidate.alternative_explanations.map((item) => <li key={item}>• {item}</li>)}
                </ul>
              </div>
            ) : null}
            {dossier?.suggested_follow_up && (
              <p className="mt-4 border-t border-[#1e314b] pt-3 text-xs leading-5 text-mute">
                <strong className="text-[#dce7f4]">Suggested follow-up:</strong> {dossier.suggested_follow_up}
              </p>
            )}
          </section>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
