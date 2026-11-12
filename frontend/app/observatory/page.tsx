import type { Metadata } from 'next';
import ObservatoryClient from '../../components/ObservatoryClient';
import { candidates, observationCatalog, researchSummary, robustness } from '../../lib/data';

export const metadata: Metadata = {
  title: 'Research Observatory | LIMEN',
  description: 'Explore all 200 LIMEN DESI observations on the sky and investigate the 39 Phase 6 evidence dossiers.',
};

export default async function ObservatoryPage() {
  const [observations, candidatesData, robustnessData, research] = await Promise.all([
    observationCatalog(),
    candidates(),
    robustness(),
    researchSummary(),
  ]);
  return <ObservatoryClient observations={observations} candidates={candidatesData} robustness={robustnessData} research={research} />;
}
