import csv
from pathlib import Path

PROJECT_ROOT = Path('/Users/vimuktha/Desktop/LIMEN')
ANOMALY_CSV = PROJECT_ROOT / 'experiments' / 'results' / 'anomaly_scores.csv'
CAND_EVIDENCE = PROJECT_ROOT / 'experiments' / 'results' / 'evidence' / 'candidate_evidence.csv'
REPORT_MD = PROJECT_ROOT / 'experiments' / 'results' / 'candidate_investigation' / 'CANDIDATE_SELECTION_REPORT.md'

def load_anomaly():
    data = {}
    with open(ANOMALY_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spec = row['specid']
            data[spec] = row
    return data

def load_candidates():
    cand = set()
    with open(CAND_EVIDENCE, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cand.add(row['specid'])
    return cand

def quality_label(row):
    try:
        spf = float(row.get('spectral_valid_pixel_fraction') or row.get('valid_pixel_fraction') or 0)
        snr = float(row.get('spectral_snr_abs_p90') or row.get('snr_abs_p90') or 0)
        img_inv = float(row.get('image_invalid_fraction') or 0)
        if spf > 0.9 and snr > 20 and img_inv < 0.1:
            return 'Minimal known concern'
        if spf > 0.7 and snr > 10:
            return 'Moderate concern'
        return 'Significant concern'
    except Exception:
        return 'Unassessed'

def select_controls(anomaly_data, candidate_set):
    eligible = []
    for spec, row in anomaly_data.items():
        if spec in candidate_set:
            continue
        # ensure ranks exist and are numeric
        try:
            s_rank = int(row['spectral_rank'])
            i_rank = int(row['image_rank'])
            m_rank = int(row['multimodal_rank'])
        except Exception:
            continue
        # exclude top-20 in any detector
        if min(s_rank, i_rank, m_rank) <= 20:
            continue
        # quality check
        q = quality_label(row)
        if q == 'Significant concern' or q == 'Unassessed':
            continue
        # compute sum for simple ordering (transparent)
        rank_sum = s_rank + i_rank + m_rank
        eligible.append((rank_sum, spec, s_rank, i_rank, m_rank, q, row))
    # sort by rank sum then by multimodal rank
    eligible.sort(key=lambda x: (x[0], x[4]))
    controls = eligible[:3]
    return controls

def rebuild_report():
    anomaly = load_anomaly()
    candidates = load_candidates()
    # verify counts
    total_obs = len(anomaly)
    cand_count = len(candidates)
    non_cand = total_obs - cand_count
    # pick controls
    controls = select_controls(anomaly, candidates)
    # Build markdown sections for controls
    control_lines = []
    control_lines.append('## Reference Control Group (3)')
    headers = ['specid','targetid','spectral_rank','image_rank','multimodal_rank','quality','spectral_valid_pixel_fraction','spectral_snr_abs_p90','image_invalid_fraction']
    control_lines.append('| ' + ' | '.join(headers) + ' |')
    control_lines.append('| ' + ' | '.join(['---']*len(headers)) + ' |')
    for _, spec, s_rank, i_rank, m_rank, q, row in controls:
        line = f"| {spec} | {row.get('targetid','')} | {s_rank} | {i_rank} | {m_rank} | {q} | {row.get('spectral_valid_pixel_fraction','')} | {row.get('spectral_snr_abs_p90','')} | {row.get('image_invalid_fraction','')} |"
        control_lines.append(line)
    # Read existing report
    with open(REPORT_MD, 'r') as f:
        report = f.read()
    # Replace control section (everything from "## Control Group" to next heading or end)
    import re
    new_report = re.sub(r'## Control Group.*?(?=\n##|\Z)', '\n'.join(control_lines), report, flags=re.S)
    # Also ensure primary shortlist ordering corrected – we will sort lines if present
    # Find Primary shortlist table
    primary_match = re.search(r'## Primary Investigation Shortlist.*?\n\| (.+?) \|\n(\|[-| ]+\|\n)((?:\|.*\n)+)', report, flags=re.S)
    if primary_match:
        # extract rows, sort by multimodal_rank column (3rd after specid?) assuming columns: specid | multimodal_rank ...
        header = primary_match.group(1)
        sep = primary_match.group(2)
        rows_text = primary_match.group(3).strip().split('\n')
        rows = []
        for r in rows_text:
            cols = [c.strip() for c in r.strip('|').split('|')]
            # multimodal_rank is second column (index 1)
            try:
                mrank = int(cols[1])
            except Exception:
                mrank = 99999
            rows.append((mrank, r))
        rows.sort(key=lambda x: x[0])
        sorted_rows = [r for _, r in rows]
        new_primary = '## Primary Investigation Shortlist (Top 5, ordered by multimodal rank)\n' + '| ' + header + ' |\n' + sep + '\n' + '\n'.join(sorted_rows) + '\n'
        new_report = re.sub(r'## Primary Investigation Shortlist.*?(?=\n##|\Z)', new_primary, new_report, flags=re.S)
    # Write back
    with open(REPORT_MD, 'w') as f:
        f.write(new_report)
    # Print summary for user
    print('Control selection summary:')
    for c in controls:
        print(c)
    print('Counts: total_obs', total_obs, 'candidates', cand_count, 'non_candidates', non_cand)

if __name__ == '__main__':
    rebuild_report()
