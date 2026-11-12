from __future__ import annotations

import argparse, csv, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
from astropy.io import fits
from scipy.stats import kendalltau, spearmanr

from backend.anomaly.baselines import fit_isolation_forest, fit_multimodal
from backend.preprocessing.baseline_features import image_baseline_features, spectral_baseline_features
from experiments.baselines.run_baselines import CONFIG, _feature_names, _numeric_matrix
from experiments.robustness.perturbations import blur_image, contiguous_spectral_mask, degrade_image_noise, degrade_spectrum_noise, mask_image_block, reduced_spectral_coverage


SEEDS=(101,202)
LEVELS={"spectral_noise":(1.5,2.0),"spectral_mask":(.10,.25),"spectral_coverage":(.10,.25),"image_noise":(.5,1.),"image_blur":(.75,1.5),"image_mask":(.0625,.25)}


def _write_csv(path:Path, rows:list[dict[str,Any]])->None:
    fields=sorted({k for r in rows for k in r})
    with path.open('w',newline='') as h: writer=csv.DictWriter(h,fields); writer.writeheader(); writer.writerows(rows)


def _manifest(root:Path)->list[dict[str,Any]]:
    return [json.loads(line) for line in (root/'data/metadata/observations.jsonl').read_text().splitlines() if line]


def _load_pilot(root: Path) -> list[dict[str, Any]]:
    """Small pilot cache; arrays remain read-only inputs and perturbations copy them."""
    loaded = []
    for item in _manifest(root):
        identity={k:item.get(k) for k in ('specid','targetid','ra_deg','dec_deg','redshift','redshift_warning','spectype')}
        with np.load(root/item['spectrum_path']) as raw:
            spectrum={key:raw[key].copy() for key in ('wavelength','flux','ivar','mask','model')}
        with fits.open(root/item['image_path'],memmap=False) as hdus:
            loaded.append({"identity":identity,"spectrum":spectrum,"image":hdus[0].data.copy(),"bands":str(hdus[0].header.get('BANDS','grz'))})
    return loaded


def _features(pilot:list[dict[str,Any]], scenario:str, level:float, seed:int)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    spectral_rows=[]; image_rows=[]
    for index,item in enumerate(pilot):
        rng=np.random.default_rng(seed*1_000_003+index)
        identity=item['identity']; wave,flux,ivar,mask,model=(item['spectrum'][k] for k in ('wavelength','flux','ivar','mask','model'))
        if scenario=='spectral_noise': flux,ivar=degrade_spectrum_noise(flux,ivar,mask,level,rng)
        elif scenario=='spectral_mask': mask,_=contiguous_spectral_mask(wave,mask,level,rng)
        elif scenario=='spectral_coverage': wave,flux,ivar,mask,model=reduced_spectral_coverage(wave,(wave,flux,ivar,mask,model),level,'red' if seed%2 else 'blue')
        spectral_rows.append({**identity,**spectral_baseline_features(wave,flux,ivar,mask,model,bins=CONFIG['spectral_shape_bins'])})
        image=item['image']; bands=item['bands']
        if scenario=='image_noise': image=degrade_image_noise(image,level,rng)
        elif scenario=='image_blur': image=blur_image(image,level)
        elif scenario=='image_mask': image,_=mask_image_block(image,level,rng)
        image_rows.append({**identity,**image_baseline_features(image,bands)})
    return spectral_rows,image_rows


def _rank_metrics(original:np.ndarray, new:np.ndarray)->dict[str,Any]:
    old10=set(np.flatnonzero(original<=10)); old20=set(np.flatnonzero(original<=20)); new10=set(np.flatnonzero(new<=10)); new20=set(np.flatnonzero(new<=20))
    return {"spearman":float(spearmanr(original,new).statistic),"kendall":float(kendalltau(original,new).statistic),"top10_retention":int(len(old10&new10)),"top20_retention":int(len(old20&new20)),"median_abs_rank_displacement":float(np.median(np.abs(new-original))),"max_abs_rank_displacement":int(np.max(np.abs(new-original)))}


def _score(spectral_rows:list[dict[str,Any]],image_rows:list[dict[str,Any]])->dict[str,Any]:
    snames,inames=_feature_names(spectral_rows,'spec_'),_feature_names(image_rows,'img_'); smat,imat=_numeric_matrix(spectral_rows,snames),_numeric_matrix(image_rows,inames); opts={k:CONFIG[k] for k in ('random_state','n_estimators','contamination')}
    return {"spectral":fit_isolation_forest(smat,snames,**opts),"image":fit_isolation_forest(imat,inames,**opts),"multimodal":fit_multimodal(smat,snames,imat,inames,**opts)}


def run(root:Path, scenarios: tuple[str, ...] | None = None, finalize: bool = True)->dict[str,Any]:
    root=root.resolve(); out=root/'experiments/results/robustness'; out.mkdir(parents=True,exist_ok=True)
    original_rows=list(csv.DictReader((root/'experiments/results/anomaly_scores.csv').open())); original={mode:np.asarray([int(r[f'{mode}_rank']) for r in original_rows]) for mode in ('spectral','image','multimodal')}
    records=[]; summary=[]; pilot=_load_pilot(root)
    active = {key: value for key, value in LEVELS.items() if scenarios is None or key in scenarios}
    for scenario,levels in active.items():
        for level in levels:
            for seed in SEEDS:
                print(f"running {scenario} level={level} seed={seed}", flush=True)
                spectral_rows,image_rows=_features(pilot,scenario,level,seed); scored=_score(spectral_rows,image_rows)
                impacted = ('spectral','multimodal') if scenario.startswith('spectral') else ('image','multimodal')
                for mode in impacted:
                    result = scored[mode]
                    metrics=_rank_metrics(original[mode],result.ranks); entrants=[original_rows[i]['specid'] for i in np.flatnonzero((result.ranks<=20)&(original[mode]>20))]
                    summary.append({"scenario":scenario,"level":level,"seed":seed,"mode":mode,**metrics,"new_top20_specids":entrants})
                    for i,row in enumerate(original_rows): records.append({"scenario":scenario,"level":level,"seed":seed,"mode":mode,"specid":row['specid'],"original_rank":int(original[mode][i]),"degraded_rank":int(result.ranks[i]),"rank_displacement":int(result.ranks[i]-original[mode][i]),"original_score":float(row[f'{mode}_anomaly_score']),"degraded_score":float(result.scores[i]),"entered_top20_due_to_degradation":bool(result.ranks[i]<=20 and original[mode][i]>20)})
    # Missing-modality conditions deliberately have no synthetic multimodal features or new scores.
    missing=[{"condition":"both_available","spectral_baseline":"available","image_baseline":"available","multimodal_baseline":"available"},{"condition":"spectral_unavailable","spectral_baseline":"unavailable","image_baseline":"available","multimodal_baseline":"unavailable"},{"condition":"image_unavailable","spectral_baseline":"available","image_baseline":"unavailable","multimodal_baseline":"unavailable"}]
    suffix = "all" if scenarios is None else "_".join(scenarios)
    _write_csv(out/f'candidate_degradation_records_{suffix}.csv',records); (out/'missing_modality_conditions.json').write_text(json.dumps(missing,indent=2)+'\n')
    machine={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"observation_count":len(original_rows),"fixed_phase3_configuration":CONFIG,"seeds":list(SEEDS),"levels":LEVELS,"assumptions":{"spectral_noise":"additional independent Gaussian noise uses variance (alpha²-1)/ivar on valid unmasked pixels; effective ivar becomes ivar/alpha².","spectral_mask":"one random contiguous interval is marked masked per spectrum.","spectral_coverage":"a blue or red edge is omitted in-memory; seed selects side.","image_noise":"per-band Gaussian noise uses robust MAD outer-annulus background estimate.","image_blur":"Gaussian filtering is applied in-memory to finite pixels.","image_mask":"a random square block becomes NaN; no zero replacement."},"results":summary,"missing_modality_conditions":missing,"refitting_sensitivity":{"method":"Every degraded run refits Isolation Forest, imputation, and scaling using the fixed Phase 3 hyperparameters and seed. A frozen-preprocessing/model comparison is not reported because Phase 3 persisted rankings/features but not fitted preprocessing objects; rankings should therefore be interpreted as refit-pipeline sensitivity, not frozen-model robustness."},"limitations":["These controlled perturbations do not represent every telescope, reduction, calibration, or astrophysical failure mode.","Stability is not scientific accuracy.","Models are refit with fixed Phase 3 hyperparameters so results measure the pipeline response to degraded inputs, not inference under a frozen training population.","No raw FITS/NPZ input was modified and Phase 3 outputs were not overwritten."]}
    (out/f'robustness_results_{suffix}.json').write_text(json.dumps(machine,indent=2)+'\n')
    lines=['# LIMEN Phase 5 controlled robustness report','',f"- Observations per scenario: {len(original_rows)}",f"- Perturbed scenarios: {len(summary)} model runs across {len(LEVELS)} perturbation families, two levels, and two seeds.",'- Phase 3 model hyperparameters and original rankings were retained as the reference.','- Missing modalities are explicitly unavailable; they are not encoded as zeros and no multimodal score is produced for those conditions.','','## Median stability by scenario and baseline','']
    for scenario in active:
        for mode in ('spectral','image','multimodal'):
            vals=[r for r in summary if r['scenario']==scenario and r['mode']==mode]
            if vals: lines.append(f"- {scenario} / {mode}: median Spearman {np.median([r['spearman'] for r in vals]):.3f}; median top-20 retention {np.median([r['top20_retention'] for r in vals]):.1f}/20")
    lines += ['', '## Refitting sensitivity','', machine['refitting_sensitivity']['method'], '', '## Limits','', *[f'- {x}' for x in machine['limitations']]]; (out/f'robustness_summary_{suffix}.md').write_text('\n'.join(lines)+'\n')
    return machine


def merge(root: Path) -> dict[str, Any]:
    out = root.resolve() / 'experiments/results/robustness'
    parts = [json.loads(path.read_text()) for path in sorted(out.glob('robustness_results_*.json')) if path.name != 'robustness_results.json']
    results = [item for part in parts for item in part['results']]
    records = [row for path in sorted(out.glob('candidate_degradation_records_*.csv')) for row in csv.DictReader(path.open())]
    _write_csv(out/'candidate_degradation_records.csv',records)
    refit = parts[0].get('refitting_sensitivity', {"method":"Every degraded run refits Isolation Forest, imputation, and scaling using fixed Phase 3 hyperparameters and seed. Fitted Phase 3 preprocessing objects were not persisted, so this is refit-pipeline sensitivity rather than frozen-model robustness."})
    merged = {"generated_at_utc":datetime.now(timezone.utc).isoformat(),"observation_count":200,"fixed_phase3_configuration":CONFIG,"parts":[path.name for path in sorted(out.glob('robustness_results_*.json')) if path.name != 'robustness_results.json'],"results":results,"missing_modality_conditions":parts[0]['missing_modality_conditions'],"refitting_sensitivity":refit,"limitations":parts[0]['limitations']}
    (out/'robustness_results.json').write_text(json.dumps(merged,indent=2)+'\n'); _plots(results,out/'ranking_stability.png')
    lines=['# LIMEN Phase 5 controlled robustness report','',f'- Observations per scenario: 200',f'- Perturbed model runs: {len(results)}.', '- Phase 3 model hyperparameters and original rankings are the fixed reference.', '- Missing modalities are explicitly unavailable and are never zero-filled.','','## Median stability by scenario and baseline','']
    for scenario in LEVELS:
        for mode in ('spectral','image','multimodal'):
            vals=[r for r in results if r['scenario']==scenario and r['mode']==mode]
            if vals: lines.append(f"- {scenario} / {mode}: median Spearman {np.median([r['spearman'] for r in vals]):.3f}; median top-20 retention {np.median([r['top20_retention'] for r in vals]):.1f}/20")
    lines += ['', '## Refitting sensitivity','', merged['refitting_sensitivity']['method'], '', '## Limits','', *[f'- {x}' for x in merged['limitations']]]; (out/'robustness_summary.md').write_text('\n'.join(lines)+'\n'); return merged


def _plots(summary:list[dict[str,Any]], path:Path)->None:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    scenarios=list(LEVELS); modes=('spectral','image','multimodal'); fig,ax=plt.subplots(figsize=(11,5))
    for mode in modes:
        vals=[]
        for scenario in scenarios:
            values=[r['spearman'] for r in summary if r['scenario']==scenario and r['mode']==mode]
            vals.append(np.median(values) if values else np.nan)
        ax.plot(scenarios,vals,marker='o',label=mode)
    ax.set(ylabel='median Spearman rank correlation to Phase 3',ylim=(-.05,1.05)); ax.tick_params(axis='x',rotation=25); ax.legend(); fig.tight_layout(); fig.savefig(path,dpi=160); plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]); parser.add_argument('--scenarios'); parser.add_argument('--merge',action='store_true'); args=parser.parse_args()
    result=merge(args.root) if args.merge else run(args.root,tuple(args.scenarios.split(',')) if args.scenarios else None); print(json.dumps({"runs":len(result['results'])},indent=2))
