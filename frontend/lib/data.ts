import fs from 'node:fs/promises';
import path from 'node:path';
import type { Candidate, Dossier, Observation } from './types';

const ROOT = path.resolve(process.cwd(), '..');
const results = (...parts: string[]) => path.join(ROOT, 'experiments', 'results', ...parts);
const metadata = (...parts: string[]) => path.join(ROOT, 'data', 'metadata', ...parts);

function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let value = '';
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') {
        value += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === ',' && !quoted) {
      row.push(value);
      value = '';
    } else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && text[index + 1] === '\n') index += 1;
      row.push(value);
      if (row.some((cell) => cell.length > 0)) rows.push(row);
      row = [];
      value = '';
    } else {
      value += char;
    }
  }

  if (value.length > 0 || row.length > 0) {
    row.push(value);
    rows.push(row);
  }

  const [headers, ...records] = rows;
  if (!headers) return [];
  return records.map((record) => Object.fromEntries(headers.map((header, index) => [header, record[index] ?? ''])));
}

const numberOrNull = (value?: string) => value == null || value.trim() === '' ? null : Number(value);
const exists = async (file: string) => fs.access(file).then(() => true, () => false);

export async function observationCatalog(): Promise<Observation[]> {
  const [manifestText, scoresText, triageText] = await Promise.all([
    fs.readFile(metadata('observations.jsonl'), 'utf8'),
    fs.readFile(results('anomaly_scores.csv'), 'utf8'),
    fs.readFile(results('triage', 'candidate_triage.csv'), 'utf8'),
  ]);
  const manifest = new Map(manifestText.split(/\r?\n/).filter(Boolean).map((line) => {
    const record = JSON.parse(line) as Record<string, unknown>;
    const exactId = (key: string) => new RegExp(`\"${key}\"\\s*:\\s*(?:\"([^\"]+)\"|(\\d+))`).exec(line)?.slice(1).find(Boolean) ?? '';
    return [exactId('specid'), { ...record, specid: exactId('specid'), targetid: exactId('targetid') } as Record<string, unknown>] as [string, Record<string, unknown>];
  }));
  const scores = parseCsv(scoresText);
  const triage = new Map(parseCsv(triageText).map((row) => [row.specid, row]));

  return Promise.all(scores.map(async (score) => {
    const specid = score.specid;
    const record = manifest.get(specid);
    if (!record) throw new Error(`Manifest coordinates missing for ${specid}`);
    const triageRow = triage.get(specid);
    const dossierPath = results('triage', 'dossiers', `${specid}.json`);
    const imagePreviewPath = results('evidence', 'plots', `${specid}.png`);
    const spectrumPath = results('frontend', 'candidates', `${specid}.json`);

    return {
      specid,
      targetid: String(record.targetid),
      ra_deg: Number(record.ra_deg),
      dec_deg: Number(record.dec_deg),
      redshift: numberOrNull(score.redshift) ?? numberOrNull(String(record.redshift)),
      spectral_score: numberOrNull(score.spectral_anomaly_score),
      spectral_rank: numberOrNull(score.spectral_rank),
      image_score: numberOrNull(score.image_anomaly_score),
      image_rank: numberOrNull(score.image_rank),
      multimodal_score: numberOrNull(score.multimodal_anomaly_score),
      multimodal_rank: numberOrNull(score.multimodal_rank),
      triage_category: triageRow?.triage_category ?? null,
      modality_relationship: triageRow?.modality_relationship ?? null,
      hasDossier: await exists(dossierPath),
      hasImagePreview: await exists(imagePreviewPath),
      hasSpectrumData: await exists(spectrumPath),
    };
  }));
}

export async function candidates(): Promise<Candidate[]> {
  const [catalog, triageText] = await Promise.all([
    observationCatalog(),
    fs.readFile(results('triage', 'candidate_triage.csv'), 'utf8'),
  ]);
  const byId = new Map(catalog.map((item) => [item.specid, item]));

  return parseCsv(triageText).map((row) => {
    const observation = byId.get(row.specid);
    if (!observation) throw new Error(`Candidate missing from observation catalog: ${row.specid}`);
    return {
      ...observation,
      spectral_rank: Number(observation.spectral_rank),
      image_rank: Number(observation.image_rank),
      multimodal_rank: Number(observation.multimodal_rank),
      spectral_score: Number(observation.spectral_score),
      image_score: Number(observation.image_score),
      multimodal_score: Number(observation.multimodal_score),
      triage_category: row.triage_category,
      modality_relationship: row.modality_relationship,
      zwarn_value: Number(row.zwarn_value),
      zwarn_flags: row.zwarn_flags,
      valid_pixel_fraction: numberOrNull(row.valid_pixel_fraction),
      snr_abs_p90: numberOrNull(row.snr_abs_p90),
      image_invalid_fraction: numberOrNull(row.image_invalid_fraction),
      residual_abs_p99: numberOrNull(row.residual_abs_p99),
      spectral_median_displacement: numberOrNull(row.spectral_median_displacement),
      image_median_displacement: numberOrNull(row.image_median_displacement),
      multimodal_median_displacement: numberOrNull(row.multimodal_median_displacement),
      spectral_top20_retention: numberOrNull(row.spectral_top20_retention),
      image_top20_retention: numberOrNull(row.image_top20_retention),
      multimodal_top20_retention: numberOrNull(row.multimodal_top20_retention),
    };
  });
}

export async function dossier(id: string): Promise<Dossier> {
  if (!/^\d+$/.test(id)) throw new Error('Invalid observation identifier');
  return JSON.parse(await fs.readFile(results('triage', 'dossiers', `${id}.json`), 'utf8'));
}

export async function researchSummary() {
  const [audit, baseline, robust, triage] = await Promise.all(['dataset_audit.json', 'baseline_results.json', 'robustness/robustness_results.json', 'triage/triage_results.json'].map(async (file) => JSON.parse(await fs.readFile(results(file), 'utf8'))));
  return { audit, baseline, robust, triage };
}

export async function robustness() {
  const raw = JSON.parse(await fs.readFile(results('robustness', 'robustness_results.json'), 'utf8'));
  return raw.results;
}

export const asset = (id: string, extension: string) => {
  if (!/^\d+$/.test(id)) throw new Error('Invalid observation identifier');
  if (extension === 'png') return results('evidence', 'plots', `${id}.png`);
  if (extension === 'json') return results('frontend', 'candidates', `${id}.json`);
  throw new Error('Unsupported asset type');
};
