export type Observation = {
  specid: string;
  targetid: string;
  ra_deg: number;
  dec_deg: number;
  redshift: number | null;
  spectral_rank: number | null;
  image_rank: number | null;
  multimodal_rank: number | null;
  spectral_score: number | null;
  image_score: number | null;
  multimodal_score: number | null;
  triage_category: string | null;
  modality_relationship: string | null;
  hasDossier: boolean;
  hasImagePreview: boolean;
  hasSpectrumData: boolean;
};

export type Candidate = {
  specid:string; targetid:string; ra_deg:number; dec_deg:number; redshift:number|null;
  spectral_rank:number; image_rank:number; multimodal_rank:number; spectral_score:number;
  image_score:number; multimodal_score:number; triage_category:string; modality_relationship:string;
  zwarn_value:number; zwarn_flags:string; valid_pixel_fraction:number|null; snr_abs_p90:number|null;
  image_invalid_fraction:number|null; residual_abs_p99:number|null; spectral_median_displacement:number|null;
  image_median_displacement:number|null; multimodal_median_displacement:number|null;
  spectral_top20_retention:number|null; image_top20_retention:number|null; multimodal_top20_retention:number|null;
  hasDossier?:boolean; hasImagePreview?:boolean; hasSpectrumData?:boolean;
};

export type SpectrumPayload = {
  specid: string;
  wavelength_angstrom: (number | null)[];
  flux: (number | null)[];
  model_flux: (number | null)[];
  standardized_residual: (number | null)[];
  masked: boolean[];
};

export type RedshiftWarning = {
  value: number;
  flags: { name: string; description: string }[];
};

export type ImageEvidence = {
  bands: string;
  quality_and_proxy_metrics: Record<string, unknown>;
  per_band_statistics: Record<string, Record<string, unknown>>;
};

export type Phase4Dossier = {
  specid: string;
  targetid: string;
  coordinates: { ra_deg: number; dec_deg: number };
  redshift: number | null;
  redshift_warning: RedshiftWarning;
  phase_3_scores_and_ranks: Record<string, number>;
  modality_relationship: string;
  spectral_quality: Record<string, unknown>;
  model_discrepancy: Record<string, unknown>;
  image_evidence: ImageEvidence;
  limitations?: string[];
  alternative_explanations?: string[];
  recommended_follow_up?: string;
  plot?: string;
};

export type CandidateRobustness = {
  availability: string;
  runs?: number;
  median_absolute_rank_displacement?: number;
  max_absolute_rank_displacement?: number;
  top20_retention_fraction?: number;
  entered_top20_due_to_degradation_count?: number;
  scenarios?: string[];
  interpretation?: string;
};

export type Dossier = {
  candidate: Phase4Dossier;
  evidence_dimensions: {
    anomaly_evidence?: Record<string, number>;
    observational_reliability?: {
      spectral?: Record<string, unknown>;
      image?: Record<string, unknown>;
      zwarn?: RedshiftWarning;
    };
    model_discrepancy?: Record<string, unknown>;
    cross_modal_relationship?: string;
    robustness: Record<string, CandidateRobustness | string>;
    missing_modality_behavior?: string;
  };
  triage: {
    category: string;
    reasons: string[];
    remaining_uncertainties: string[];
    interpretation_boundary: string;
  };
  suggested_follow_up: string;
  phase4?: Phase4Dossier | null;
};

export type RobustnessRun = {
  scenario: string;
  level: number;
  seed: number;
  mode: 'spectral' | 'image' | 'multimodal';
  spearman: number;
  kendall: number;
  top10_retention: number;
  top20_retention: number;
  median_abs_rank_displacement: number;
  max_abs_rank_displacement: number;
  new_top20_specids: string[];
};
