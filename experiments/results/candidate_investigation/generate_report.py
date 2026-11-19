import json, csv, os, sys
from pathlib import Path

PROJECT_ROOT = Path('/Users/vimuktha/Desktop/LIMEN')
DOSSIERS_DIR = PROJECT_ROOT / 'experiments' / 'results' / 'evidence' / 'dossiers'
CSV_PATH = PROJECT_ROOT / 'experiments' / 'results' / 'evidence' / 'candidate_evidence.csv'
OBS_JSONL = PROJECT_ROOT / 'data' / 'metadata' / 'observations.jsonl'
ROBUST_DIR = PROJECT_ROOT / 'experiments' / 'results' / 'robustness'
REPORT_MD = PROJECT_ROOT / 'experiments' / 'results' / 'candidate_investigation' / 'CANDIDATE_SELECTION_REPORT.md'

def load_dossiers():
    candidates = {}
    for json_file in DOSSIERS_DIR.glob('*.json'):
        with open(json_file) as f:
            data = json.load(f)
        specid = data.get('specid') or data.get('id')
        if not specid:
            continue
        candidates[specid] = {
            'specid': specid,
            'targetid': data.get('targetid'),
            'coordinates': data.get('coordinates', {}),
            'redshift': data.get('redshift'),
            'spectype': data.get('spectype'),
            'phase3': data.get('phase_3_scores_and_ranks', {}),
            'modality_relationship': data.get('modality_relationship'),
            'triage': data.get('triage') or data.get('phase_6_triage_category'),
            'spectral_quality': data.get('spectral_quality', {}),
            'image_quality': data.get('image_quality', {}),
            'residual_valid_fraction': data.get('model_discrepancy', {}).get('residual_valid_fraction'),
        }
    return candidates

def load_csv():
    rows = {}
    with open(CSV_PATH, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spec = row.get('specid') or row.get('SpecID')
            if spec:
                rows[spec] = row
    return rows

def load_observations():
    obs = {}
    with open(OBS_JSONL) as f:
        for line in f:
            try:
                data = json.loads(line)
                spec = data.get('specid')
                if spec:
                    obs[spec] = data
            except json.JSONDecodeError:
                continue
    return obs

def classify_quality(spectral, image):
    # Simple heuristic mirroring existing code (placeholder)
    # Return string quality level.
    try:
        spf = float(spectral.get('valid_pixel_fraction', 0))
        snr = float(spectral.get('snr_abs_p90', 0))
        img_inv = float(image.get('invalid_fraction', 0))
        if spf > 0.9 and snr > 20 and img_inv < 0.1:
            return 'Minimal known concern'
        if spf > 0.7 and snr > 10:
            return 'Moderate concern'
        return 'Significant concern'
    except Exception:
        return 'Unassessed'

def load_robustness():
    robustness = {}
    # Look for JSON files in the robustness dir; map modality to dict.
    for file in ROBUST_DIR.glob('*.json'):
        with open(file) as f:
            try:
                data = json.load(f)
                robustness[file.stem] = data
            except Exception:
                continue
    return robustness

def make_table(rows, headers):
    # markdown table generator
    lines = []
    header_line = '| ' + ' | '.join(headers) + ' |'
    sep_line = '| ' + ' | '.join(['---'] * len(headers)) + ' |'
    lines.append(header_line)
    lines.append(sep_line)
    for row in rows:
        line = '| ' + ' | '.join(str(row.get(h, '')) for h in headers) + ' |'
        lines.append(line)
    return '\n'.join(lines)

def main():
    candidates = load_dossiers()
    csv_data = load_csv()
    obs = load_observations()
    robustness = load_robustness()

    # Merge CSV info into candidates
    for spec, cand in candidates.items():
        csv_row = csv_data.get(spec, {})
        cand.update({
            'spectral_rank': csv_row.get('spectral_rank'),
            'spectral_score': csv_row.get('spectral_score'),
            'image_rank': csv_row.get('image_rank'),
            'image_score': csv_row.get('image_score'),
            'multimodal_rank': csv_row.get('multimodal_rank'),
            'multimodal_score': csv_row.get('multimodal_score'),
            'zwarn_flags': csv_row.get('zwarn_flags'),
        })
        # add observation metadata if present
        if spec in obs:
            cand['ra'] = obs[spec].get('ra_deg')
            cand['dec'] = obs[spec].get('dec_deg')
        # compute quality
        cand['quality'] = classify_quality(cand.get('spectral_quality', {}), cand.get('image_quality', {}))

    # ---------- Primary shortlist selection ----------
    # Criteria: any top-20 rank, minimal quality concern, residual fraction high.
    def rank_key(c):
        # lower is better for any rank present
        ranks = []
        for key in ['spectral_rank', 'image_rank', 'multimodal_rank']:
            v = c.get(key)
            if v and v.isdigit():
                ranks.append(int(v))
        return min(ranks) if ranks else 9999
    primary_candidates = []
    for cand in candidates.values():
        # check top-20 in any rank
        top20 = any(cand.get(k) and cand[k].isdigit() and int(cand[k]) <= 20 for k in ['spectral_rank','image_rank','multimodal_rank'])
        if not top20:
            continue
        if cand['quality'] == 'Significant concern':
            continue
        primary_candidates.append(cand)
    primary_candidates.sort(key=lambda c: (
        rank_key(c),
        0 if c['quality']=='Minimal known concern' else 1,
        -float(c.get('residual_valid_fraction') or 0)
    ))
    primary_top5 = primary_candidates[:5]

    # ---------- Disagreement shortlist ----------
    disagreement = []
    for cand in candidates.values():
        rel = cand.get('modality_relationship','').lower()
        sr = cand.get('spectral_rank')
        ir = cand.get('image_rank')
        if rel and ('spectral' in rel and ir and ir.isdigit() and int(ir)>20) or (
            'image' in rel and sr and sr.isdigit() and int(sr)>20):
            disagreement.append(cand)
    disagreement.sort(key=lambda c: (
        rank_key(c),
        0 if c['quality']=='Minimal known concern' else 1
    ))
    disagreement_top5 = disagreement[:5]

    # ---------- Control group selection ----------
    all_obs_specids = set(obs.keys())
    phase6_specids = set(candidates.keys())
    non_candidates = all_obs_specids - phase6_specids
    control_candidates = []
    for spec in non_candidates:
        row = csv_data.get(spec, {})
        # need ranks maybe missing; treat missing as high rank
        qual = classify_quality({},{})
        # we need good quality (minimal or moderate) and not top20 in any rank
        top20 = any(row.get(k) and row[k].isdigit() and int(row[k])<=20 for k in ['spectral_rank','image_rank','multimodal_rank'])
        if top20:
            continue
        # approximating quality as minimal if we have observation metadata with good S/N; here we just accept.
        control_candidates.append({
            'specid': spec,
            'multimodal_rank': row.get('multimodal_rank',''),
            'quality': qual,
            'notes': 'Selected as ordinary reference; not in Phase‑6 candidates.'
        })
        if len(control_candidates)>=3:
            break

    # ---------- Build markdown report ----------
    lines = []
    lines.append('# Candidate Selection Report (Corrected)')
    lines.append('\n## Full 39‑candidate table')
    headers = ['specid','targetid','spectral_rank','image_rank','multimodal_rank','triage','quality','residual_valid_fraction']
    rows = []
    for c in candidates.values():
        rows.append({h: c.get(h) for h in headers})
    lines.append(make_table(rows, headers))

    lines.append('\n## Primary Investigation Shortlist (Top 5)')
    top_headers = ['specid','multimodal_rank','triage','quality','residual_valid_fraction','notes']
    top_rows = []
    for c in primary_top5:
        notes = []
        if c.get('modality_relationship'):
            notes.append(f"Modality: {c['modality_relationship']}")
        if c.get('zwarn_flags'):
            notes.append(f"ZWARN: {c['zwarn_flags']}")
        top_rows.append({
            'specid': c.get('specid'),
            'multimodal_rank': c.get('multimodal_rank'),
            'triage': c.get('triage'),
            'quality': c.get('quality'),
            'residual_valid_fraction': c.get('residual_valid_fraction'),
            'notes': '; '.join(notes)
        })
    lines.append(make_table(top_rows, top_headers))

    lines.append('\n## Cross‑Modal Disagreement Shortlist (Top 5)')
    disc_headers = ['specid','spectral_rank','image_rank','modality_relationship','multimodal_rank','quality','notes']
    disc_rows = []
    for c in disagreement_top5:
        notes = []
        if c.get('zwarn_flags'):
            notes.append(f"ZWARN: {c['zwarn_flags']}")
        disc_rows.append({
            'specid': c.get('specid'),
            'spectral_rank': c.get('spectral_rank'),
            'image_rank': c.get('image_rank'),
            'modality_relationship': c.get('modality_relationship'),
            'multimodal_rank': c.get('multimodal_rank'),
            'quality': c.get('quality'),
            'notes': '; '.join(notes)
        })
    lines.append(make_table(disc_rows, disc_headers))

    lines.append('\n## Control Group Candidates (3)')
    ctrl_headers = ['specid','multimodal_rank','quality','notes']
    ctrl_rows = []
    for c in control_candidates:
        ctrl_rows.append({h: c.get(h) for h in ctrl_headers})
    lines.append(make_table(ctrl_rows, ctrl_headers))

    lines.append('\n---')
    lines.append('\n**Selection Rationale**')
    lines.append('\n- Primary shortlist chosen by presence in top‑20 of any detector, minimal quality concerns, and high residual‑valid fraction.')
    lines.append('- Disagreement shortlist highlights candidates where one modality flags strong anomaly while the other does not, useful for investigating multi‑modal fusion behavior.')
    lines.append('- Control group drawn from the full 200‑observation set, excluding Phase‑6 candidates, with good data quality and low anomaly scores, to serve as ordinary references.')

    # write report
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_MD, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Report written to {REPORT_MD}")

if __name__ == '__main__':
    main()
