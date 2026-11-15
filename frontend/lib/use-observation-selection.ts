'use client';

import { useCallback, useEffect, useState } from 'react';
import { observationUrl, selectedSpecid } from './observation-selection';

export function useObservationSelection() {
  const [specid, setSpecid] = useState<string | null>(null);

  useEffect(() => {
    const syncFromAddressBar = () => setSpecid(selectedSpecid(window.location.search));
    syncFromAddressBar();
    window.addEventListener('popstate', syncFromAddressBar);
    return () => window.removeEventListener('popstate', syncFromAddressBar);
  }, []);

  const selectSpecid = useCallback((nextSpecid: string | null) => {
    const nextUrl = observationUrl(window.location.pathname, window.location.search, window.location.hash, nextSpecid);
    window.history.pushState(null, '', nextUrl);
    setSpecid(nextSpecid);
  }, []);

  return { specid, selectSpecid };
}
