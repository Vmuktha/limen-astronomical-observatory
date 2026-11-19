import { describe, expect, it } from 'vitest';
import { candidates, dossier, observationCatalog } from './data';

describe('joined DESI observation catalog', () => {
  it('includes all 200 phase-2 rows, unique exact specids, and the 39 existing Phase 6 dossiers', async () => {
    const observations = await observationCatalog();
    expect(observations).toHaveLength(200);
    expect(new Set(observations.map((item) => item.specid)).size).toBe(200);
    expect(observations.filter((item) => item.hasDossier)).toHaveLength(39);
    expect(observations.filter((item) => item.hasImagePreview)).toHaveLength(39);
    expect(observations.every((item) => Number.isFinite(item.ra_deg) && item.ra_deg >= 0 && item.ra_deg < 360 && Number.isFinite(item.dec_deg) && item.dec_deg >= -90 && item.dec_deg <= 90)).toBe(true);
    expect(observations.find((item) => item.specid === '39627948025709214')).toMatchObject({
      specid: '39627948025709214',
      targetid: '39627948025709214',
      ra_deg: expect.any(Number),
      dec_deg: expect.any(Number),
      spectral_rank: expect.any(Number),
      image_rank: expect.any(Number),
      multimodal_rank: expect.any(Number),
    });
    expect(observations.find((item) => !item.hasDossier)).toMatchObject({ triage_category: null, hasDossier: false });
  });

  it('joins the real Phase 4 diagnostics to the Phase 6 interpretation dossier', async () => {
    const record = await dossier('39627432617054050');
    expect(record.candidate.specid).toBe('39627432617054050');
    expect(record.phase4?.spectral_quality.samples).toBe(7781);
    expect(record.phase4?.spectral_quality.mask_nonzero_fraction).toBeCloseTo(0.0046266547, 8);
    expect(record.phase4?.model_discrepancy.discrepancy_regions).toHaveLength(1);
    expect(record.evidence_dimensions.robustness.multimodal).toMatchObject({ runs: 24 });
    expect(record.triage.interpretation_boundary).toContain('not');
  });

  it('matches the exact Phase 6 roster and handles all missing previews explicitly', async () => {
    const [observations, phase6] = await Promise.all([observationCatalog(), candidates()]);
    const dossierIds = observations.filter((item) => item.hasDossier).map((item) => item.specid).sort();
    expect(phase6).toHaveLength(39);
    expect(phase6.map((item) => item.specid).sort()).toEqual(dossierIds);
    expect(observations.filter((item) => !item.hasImagePreview)).toHaveLength(161);
    expect(observations.filter((item) => !item.hasDossier).every((item) => !item.hasImagePreview)).toBe(true);
  });
});
