'use client';

import { useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import type { Observation } from '../lib/types';

function point(observation: Observation): [number, number, number] {
  const ra = observation.ra_deg * Math.PI / 180;
  const dec = observation.dec_deg * Math.PI / 180;
  const radius = 4.2;
  return [radius * Math.cos(dec) * Math.cos(ra), radius * Math.sin(dec), radius * Math.cos(dec) * Math.sin(ra)];
}

function observationColor(observation: Observation) {
  if (!observation.hasDossier) return '#718199';
  if (observation.triage_category?.startsWith('Multimodal')) return '#f2c977';
  if (observation.triage_category?.startsWith('Evidence')) return '#e8899b';
  if (observation.triage_category?.startsWith('Spectral')) return '#83d6d2';
  return '#a8b7ca';
}

function Points({ observations, selectedId, onPick }: { observations: Observation[]; selectedId: string | null; onPick: (specid: string) => void }) {
  return <>{observations.map((observation) => {
    const position = point(observation);
    const selected = observation.specid === selectedId;
    return <mesh key={observation.specid} position={position} onClick={(event) => { event.stopPropagation(); onPick(observation.specid); }}>
      <sphereGeometry args={[selected ? 0.12 : observation.hasDossier ? 0.075 : 0.045, 10, 10]} />
      <meshBasicMaterial color={selected ? '#ffffff' : observationColor(observation)} />
    </mesh>;
  })}</>;
}

export default function SkyScene({ observations, selectedId, onPick }: { observations: Observation[]; selectedId: string | null; onPick: (specid: string) => void }) {
  const [view, setView] = useState(0);
  return <div className="relative h-[380px] overflow-hidden rounded-xl border border-[#1e314b]">
    <Canvas key={view} camera={{ position: [0, 0, 7], fov: 48 }} dpr={[1, 1.35]}>
      <color attach="background" args={['#070b14']} />
      <ambientLight intensity={0.4} />
      <Stars radius={35} depth={20} count={900} factor={1.3} saturation={0} fade speed={0.2} />
      <Points observations={observations} selectedId={selectedId} onPick={onPick} />
      <OrbitControls enablePan={false} minDistance={4.8} maxDistance={11} />
    </Canvas>
    <p className="pointer-events-none absolute left-3 top-3 rounded-md bg-[#07101c]/70 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-[#b9c8d8]">200 observations <span className="mx-1 text-[#647990]">/</span> 39 Phase 6 dossiers</p>
    <button aria-label="Reset sky view" onClick={() => setView((value) => value + 1)} className="absolute bottom-3 right-3 rounded-md border border-[#365471] bg-[#07101c]/90 px-3 py-1.5 text-xs text-[#e5edf7] hover:border-cyan">Reset view</button>
  </div>;
}
