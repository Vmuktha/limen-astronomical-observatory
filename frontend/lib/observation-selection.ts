export function selectedSpecid(search: string): string | null {
  const value = new URLSearchParams(search).get('specid');
  return value && /^\d+$/.test(value) ? value : null;
}

export function observationUrl(pathname: string, currentSearch: string, hash: string, specid: string | null) {
  const params = new URLSearchParams(currentSearch);
  if (specid) params.set('specid', specid);
  else params.delete('specid');
  const query = params.toString();
  return `${pathname}${query ? `?${query}` : ''}${hash}`;
}
