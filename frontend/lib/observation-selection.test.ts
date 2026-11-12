import { describe, expect, it } from 'vitest';
import { observationUrl, selectedSpecid } from './observation-selection';

describe('observation URL identity', () => {
  it('reads the selected DESI specid from the shared query parameter', () => {
    expect(selectedSpecid('?specid=39627948025709214')).toBe('39627948025709214');
    expect(selectedSpecid('?specid=not-a-specid')).toBeNull();
  });

  it('preserves other query parameters and the Evidence Laboratory anchor', () => {
    expect(observationUrl('/observatory', '?view=sky', '#evidence', '39627948025709214'))
      .toBe('/observatory?view=sky&specid=39627948025709214#evidence');
  });
});
