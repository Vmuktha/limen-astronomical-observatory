from __future__ import annotations

import argparse, csv, json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.prioritization.triage import RULES, robustness_summary, triage


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields=sorted({key for row in rows for key in row})
    with path.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fields); writer.writeheader(); writer.writerows(rows)


def run(root: Path) -> dict[str, Any]:
    root=root.resolve(); evidence=root/'experiments/results/evidence'; output=root/'experiments/results/triage'; output.mkdir(parents=True,exist_ok=True); dossier_out=output/'dossiers'; dossier_out.mkdir(exist_ok=True)
    robustness=defaultdict(list)
    for row in csv.DictReader((root/'experiments/results/robustness/candidate_degradation_records.csv').open()): robustness[row['specid']].append(row)
    output_rows=[]; category_counts=Counter()
    for source in sorted((evidence/'dossiers').glob('*.json')):
        dossier=json.loads(source.read_text()); records=robustness.get(dossier['specid'],[])
        spec=robustness_summary(records,'spectral'); image=robustness_summary(records,'image'); multi=robustness_summary(records,'multimodal')
        category,reasons,uncertainties=triage(dossier,spec,image,multi)
        unified={"candidate":dossier,"evidence_dimensions":{"anomaly_evidence":dossier['phase_3_scores_and_ranks'],"observational_reliability":{"spectral":dossier['spectral_quality'],"image":dossier['image_evidence']['quality_and_proxy_metrics'],"zwarn":dossier['redshift_warning']},"model_discrepancy":dossier['model_discrepancy'],"cross_modal_relationship":dossier['modality_relationship'],"robustness":{"spectral":spec,"image":image,"multimodal":multi,"missing_modality_behavior":"No multimodal score exists when either modality is unavailable; modalities are never zero-filled."}},"triage":{"category":category,"reasons":reasons,"remaining_uncertainties":uncertainties,"rule_definitions":RULES,"interpretation_boundary":"Rule-based workflow category only; it is not a weighted priority score, probability, astrophysical significance, or discovery claim."},"suggested_follow_up":"Review the source Phase 4 spectrum/model/residual and image dossier; inspect measurement quality and method limitations before any physical interpretation."}
        (dossier_out/f"{dossier['specid']}.json").write_text(json.dumps(unified,indent=2)+"\n")
        ranks=dossier['phase_3_scores_and_ranks']; output_rows.append({"specid":dossier['specid'],"targetid":dossier['targetid'],"triage_category":category,"triage_reasons":"; ".join(reasons),"spectral_rank":ranks['spectral_rank'],"image_rank":ranks['image_rank'],"multimodal_rank":ranks['multimodal_rank'],"spectral_score":ranks['spectral_anomaly_score'],"image_score":ranks['image_anomaly_score'],"multimodal_score":ranks['multimodal_anomaly_score'],"modality_relationship":dossier['modality_relationship'],"zwarn_value":dossier['redshift_warning']['value'],"zwarn_flags":";".join(x['name'] for x in dossier['redshift_warning']['flags']),"valid_pixel_fraction":dossier['spectral_quality']['valid_pixel_fraction'],"snr_abs_p90":dossier['spectral_quality']['snr_abs_p90'],"image_invalid_fraction":dossier['image_evidence']['quality_and_proxy_metrics']['image_invalid_fraction'],"residual_abs_p99":dossier['model_discrepancy']['standardized_residual_abs_p99'],"spectral_median_displacement":spec.get('median_absolute_rank_displacement'),"spectral_top20_retention":spec.get('top20_retention_fraction'),"image_median_displacement":image.get('median_absolute_rank_displacement'),"image_top20_retention":image.get('top20_retention_fraction'),"multimodal_median_displacement":multi.get('median_absolute_rank_displacement'),"multimodal_top20_retention":multi.get('top20_retention_fraction'),"source_phase4_dossier":str(source.relative_to(root))})
        category_counts[category]+=1
    output_rows.sort(key=lambda row:row['multimodal_rank']); write_csv(output/'candidate_triage.csv',output_rows)
    methodology=['# LIMEN Phase 6 triage methodology','', '## Design', '', 'This is a rule-based investigation workflow. It deliberately produces categories and reasons, not a weighted score, priority number, probability, or discovery assertion.', '', '## Rules', '']
    methodology += [f"- **{key}** — {value}" for key,value in RULES.items()]
    methodology += ['', '## Evidence safeguards','', '- Original Phase 3 scores and rankings are copied unchanged.', '- ZWARN is retained as an integer and decoded flags; it is not collapsed into a generic quality score.', '- Model discrepancy is included once as mask-aware residual context and is never called physical-model failure.', '- Robustness records are refit-pipeline sensitivity under controlled degradation, not frozen-model robustness or scientific accuracy.', '- A missing modality has no multimodal score; it is never substituted with zeros.', '- Legacy Survey comparison is cross-survey consistency evidence, not independent confirmation.']
    (output/'methodology.md').write_text('\n'.join(methodology)+'\n')
    result={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"candidate_count":len(output_rows),"category_counts":dict(category_counts),"rules":RULES,"comparison":{"conventional_order":"Phase 3 multimodal rank ascending", "evidence_aware_workflow":"Triage category plus its explicit reasons; no reordered numeric priority list is created.","top20_multimodal_categories":[{"specid":row['specid'],"rank":row['multimodal_rank'],"category":row['triage_category']} for row in output_rows if row['multimodal_rank']<=20]},"limitations":["This is a workflow comparison, not proof of improved astrophysical accuracy.","A rule threshold is an explicit operational choice, not an empirical probability.","The input is a small GALAXY-only pilot and cannot support population-level conclusions."]}
    (output/'triage_results.json').write_text(json.dumps(result,indent=2)+'\n'); _plots(output_rows,output/'triage_summary.png')
    report=['# LIMEN Phase 6 evidence-aware candidate triage','',f"- Unified dossiers: {len(output_rows)}",'- No weighted priority score or new anomaly ranking was created.','- Conventional multimodal rank is preserved and compared to rule-based investigation categories.','','## Category counts','',*[f'- {key}: {value}' for key,value in sorted(category_counts.items())],'','## Workflow comparison','', 'Highly ranked multimodal candidates can be inspected with their triage category and reasons before proceeding. The triage output intentionally does not impose a replacement numeric order; it exposes modality specificity, evidence sensitivity, and available diagnostics.', '', '## Limits','', *[f'- {item}' for item in result['limitations']]]
    (output/'comparative_analysis.md').write_text('\n'.join(report)+'\n'); return result


def _plots(rows:list[dict[str,Any]], path:Path)->None:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    categories=sorted(set(row['triage_category'] for row in rows)); counts=[sum(row['triage_category']==c for row in rows) for c in categories]
    fig,ax=plt.subplots(figsize=(9,4)); ax.barh(categories,counts,color='#547a94'); ax.set(xlabel='candidates',title='Evidence-aware triage categories'); fig.tight_layout(); fig.savefig(path,dpi=160); plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]); args=parser.parse_args(); print(json.dumps(run(args.root),indent=2))
