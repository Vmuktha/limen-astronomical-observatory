import { describe, expect, it } from 'vitest';
import { robustness } from './data';
import { median, summarizeRobustness } from './robustness-summary';

describe('Phase 5 robustness summaries', () => {
  it('computes an even-count median without selecting the upper middle value', () => {
    expect(median([5, 1, 9, 3])).toBe(4);
  });

  it('groups the actual 48 runs by perturbation family and baseline mode', async () => {
    const runs = await robustness();
    const summaries = summarizeRobustness(runs);

    expect(runs).toHaveLength(48);
    expect(new Set(runs.map((run) => run.scenario)).size).toBe(6);
    expect(summaries).toHaveLength(12);
    expect(summaries.every((summary) => summary.runCount === 4)).toBe(true);

    const imageNoiseMultimodal = summaries.find(
      (summary) => summary.scenario === 'image_noise' && summary.mode === 'multimodal',
    );
    expect(imageNoiseMultimodal).toMatchObject({
      runCount: 4,
      levels: [0.5, 1],
      seeds: [101, 202],
      medianTop20Retention: 19.5,
    });
    expect(imageNoiseMultimodal?.medianSpearman).toBeCloseTo(0.991542, 5);
  });
});
