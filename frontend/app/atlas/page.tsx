import type { Metadata } from 'next';
import AtlasExplorer from '../../components/AtlasExplorer';
import { observationCatalog } from '../../lib/data';

export const metadata: Metadata = {
  title: 'Galaxy Atlas | LIMEN',
  description: 'Explore all 200 LIMEN DESI DR1 observations, anomaly ranks, sky coordinates and Phase 6 investigation status.',
};

export default async function AtlasPage() {
  const observations = await observationCatalog();
  return <AtlasExplorer observations={observations} />;
}
