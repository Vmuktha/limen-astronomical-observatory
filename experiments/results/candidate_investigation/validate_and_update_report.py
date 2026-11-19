import csv, json, os
from pathlib import Path

PROJECT_ROOT = Path('/Users/vimuktha/Desktop/LIMEN')
DOSSIERS_DIR = PROJECT_ROOT / 'experiments' / 'results' / 'evidence' / 'dossiers'
TRIAGE_CSV = PROJECT_ROOT / 'experiments' / 'results' / 'triage' / 'candidate_triage.csv'
CSV_PATH = PROJECT_ROOT / 'experiments' / 'results' / 'evidence' / 'candidate_evidence.csv'
REPORT_MD = PROJECT_ROOT / 'experiments' / 'results' / 'candidate_investigation' / 'CANDIDATE_SELECTION_REPORT.md'

def load_dossiers():
    candidates = {}
    for fp in DOSSIERS_DIR.glob('*.json'):
        with open(fp) as f:
            data = json.load(f)
        specid = data.get('specid')
        if not specid:
            continue
        candidates[specid] = {
            'specid': specid,
            'targetid': data.get('targetid'),
            'phase3': data.get('phase_3_scores_and_ranks', {}),
            'modality_relationship': data.get('modality_relationship'),
            'spectral_quality': data.get('spectral_quality', {}),
            'image_quality': data.get('image_evidence', {}).get('quality_and_proxy_metrics', {}),
            'residual_valid_fraction': data.get('model_discrepancy', {}).get('residual_valid_fraction'),
        }
    return candidates

def load_triage_csv():
    triage_map = {}
    with open(TRIAGE_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spec = row.get('specid') or row.get('SpecID')
            if spec:
                triage_map[spec] = row.get('triage_category')
    return triage_map

def load_csv():
    rows = {}
    with open(CSV_PATH, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spec = row.get('specid') or row.get('SpecID')
            if spec:
                rows[spec] = row
    return rows

def classify_quality(spectral_q, image_q, csv_row=None):
    # Use same heuristic as before, augmented with CSV values if provided
    try:
        spf = float(spectral_q.get('valid_pixel_fraction', csv_row.get('valid_pixel_fraction', 0) if csv_row else 0))
        snr = float(spectral_q.get('snr_abs_p90', csv_row.get('snr_abs_p90', 0) if csv_row else 0))
        img_inv = float(image_q.get('image_invalid_fraction', csv_row.get('image_invalid_fraction', 0) if csv_row else 0))
        if spf > 0.9 and snr > 20 and img_inv < 0.1:
            return 'Minimal known concern'
        if spf > 0.7 and snr > 10:
            return 'Moderate concern'
        return 'Significant concern'
    except Exception:
        return 'Unassessed'

def make_table(rows, headers):
    lines = []
    header_line = '| ' + ' | '.join(headers) + ' |'
    sep_line = '| ' + ' | '.join(['---'] * len(headers)) + ' |'
    lines.append(header_line)
    lines.append(sep_line)
    for r in rows:
        line = '| ' + ' | '.join(str(r.get(h, '')) for h in headers) + ' |'
        lines.append(line)
    return '\n'.join(lines)

def main():
    candidates = load_dossiers()
    triage_map = load_triage_csv()
    csv_data = load_csv()

    # Merge CSV and triage into candidate dicts
    for spec, cand in candidates.items():
        row = csv_data.get(spec, {})
        cand.update({
            'spectral_rank': row.get('spectral_rank'),
            'image_rank': row.get('image_rank'),
            'multimodal_rank': row.get('multimodal_rank'),
            'zwarn_flags': row.get('zwarn_flags'),
            'valid_pixel_fraction': row.get('valid_pixel_fraction'),
            'mask_nonzero_fraction': row.get('mask_nonzero_fraction'),
            'snr_abs_p90': row.get('snr_abs_p90'),
            'image_invalid_fraction': row.get('image_invalid_fraction'),
        })
        cand['triage'] = triage_map.get(spec, None)
        cand['quality'] = classify_quality(cand.get('spectral_quality'), cand.get('image_quality'), row)

    # -------- Primary shortlist (top-5) --------
    def any_top20(c):
        for k in ['spectral_rank','image_rank','multimodal_rank']:
            v = c.get(k)
            if v and v.isdigit() and int(v) <= 20:
                return True
        return False
    primary = [c for c in candidates.values() if any_top20(c) and c['quality']!='Significant concern']
    primary.sort(key=lambda c: (
        min(int(c[k]) for k in ['spectral_rank','image_rank','multimodal_rank'] if c.get(k) and c[k].isdigit()),
        0 if c['quality']=='Minimal known concern' else 1,
        -float(c.get('residual_valid_fraction') or 0)
    ))
    primary_top5 = primary[:5]

    # -------- Disagreement shortlist --------
    disagreement = []
    for c in candidates.values():
        rel = (c.get('modality_relationship') or '').lower()
        sr = c.get('spectral_rank')
        ir = c.get('image_rank')
        if rel.startswith('spectral') and ir and ir.isdigit() and int(ir)>20:
            disagreement.append(c)
        if rel.startswith('image') and sr and sr.isdigit() and int(sr)>20:
            disagreement.append(c)
    disagreement.sort(key=lambda c: (
        min(int(c[k]) for k in ['spectral_rank','image_rank','multimodal_rank'] if c.get(k) and c[k].isdigit()),
        0 if c['quality']=='Minimal known concern' else 1
    ))
    disagreement_top5 = disagreement[:5]

    # -------- Control group selection --------
    all_specids = set(csv_data.keys())
    candidate_specids = set(candidates.keys())
    non_candidates = all_specids - candidate_specids
    controls = []
    for spec in sorted(non_candidates):
        row = csv_data[spec]
        # require all three ranks present
        if not (row.get('spectral_rank') and row.get('image_rank') and row.get('multimodal_rank')):
            continue
        # quality assessment using CSV values only
        quality = classify_quality({}, {}, row)
        if quality == 'Significant concern':
            continue
        # avoid top20 in any rank
        if any(int(row[k])<=20 for k in ['spectral_rank','image_rank','multimodal_rank'] if row.get(k) and row[k].isdigit()):
            continue
        controls.append({
            'specid': spec,
            'multimodal_rank': row.get('multimodal_rank'),
            'spectral_rank': row.get('spectral_rank'),
            'image_rank': row.get('image_rank'),
            'quality': quality,
            'notes': 'Reference control; outside Phase‑6 candidates, low anomaly scores.'
        })
        if len(controls) >= 3:
            break

    # -------- Build report --------
    lines = []
    lines.append('# Candidate Selection Report (Corrected – Round 2)')
    lines.append('\n## Full 39‑candidate table')
    cand_headers = ['specid','targetid','spectral_rank','image_rank','multimodal_rank','triage','quality','residual_valid_fraction']
    cand_rows = []
    for c in candidates.values():
        cand_rows.append({h: c.get(h) for h in cand_headers})
    lines.append(make_table(cand_rows, cand_headers))

    lines.append('\n## Primary Investigation Shortlist (Top 5, ordered by multimodal rank)')
    prim_headers = ['specid','multimodal_rank','triage','quality','residual_valid_fraction','notes']
    prim_rows = []
    for c in primary_top5:
        notes = []
        if c.get('modality_relationship'):
            notes.append(f"Modality: {c['modality_relationship']}")
        if c.get('zwarn_flags'):
            notes.append(f"ZWARN: {c['zwarn_flags']}")
        prim_rows.append({
            'specid': c.get('specid'),
            'multimodal_rank': c.get('multimodal_rank'),
            'triage': c.get('triage'),
            'quality': c.get('quality'),
            'residual_valid_fraction': c.get('residual_valid_fraction'),
            'notes': '; '.join(notes)
        })
    lines.append(make_table(prim_rows, prim_headers))

    lines.append('\n## Cross‑Modal Disagreement Shortlist (Top 5)')
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
    ctrl_headers = ['specid','spectral_rank','image_rank','multimodal_rank','quality','notes']
    ctrl_rows = []
    for c in controls:
        ctrl_rows.append({h: c.get(h) for h in ctrl_headers})
    lines.append(make_table(ctrl_rows, ctrl_headers))

    lines.append('\n---')
    lines.append('\n**Integrity Check**')
    # Simple checks
    checks = []
    checks.append(f"All 39 candidate specids present: {'PASS' if len(candidates)==39 else 'FAIL'}")
    missing_triage = [c['specid'] for c in candidates.values() if not c.get('triage')]
    checks.append(f"Triages resolved (non‑empty): {'PASS' if not missing_triage else 'FAIL'} ({len(missing_triage)} missing)")
    checks.append(f"Primary shortlist 5 entries: {'PASS' if len(primary_top5)==5 else 'FAIL'}")
    checks.append(f"Disagreement shortlist 5 entries: {'PASS' if len(disagreement_top5)==5 else 'FAIL'}")
    checks.append(f"Control group 3 entries: {'PASS' if len(controls)==3 else 'FAIL'}")
    lines.append('\n'.join(['- '+c for c in checks]))

    with open(REPORT_MD, 'w') as f:
        f.write('\n'.join(lines))
    print('Report regenerated at', REPORT_MD)

if __name__ == '__main__':
    main()
