from __future__ import annotations

import argparse, csv, json, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
from astropy.io import fits

from backend.discrepancy.residuals import residual_diagnostics
from backend.quality.metrics import image_metrics, robust_mad, safe_quantile
from backend.validation.zwarn import decode_zwarn


def _safe(value: Any) -> Any:
    if isinstance(value, dict): return {k:_safe(v) for k,v in value.items()}
    if isinstance(value, list): return [_safe(v) for v in value]
    if isinstance(value, (float,np.floating)) and not math.isfinite(value): return None
    if isinstance(value, np.integer): return int(value)
    return value


def modality_relationship(spectral_rank: int, image_rank: int, top_n: int = 20) -> str:
    if spectral_rank <= top_n and image_rank <= top_n: return "Both modalities unusual"
    if spectral_rank <= top_n: return "Spectral-dominated"
    if image_rank <= top_n: return "Image-dominated"
    return "Neither modality strongly unusual"


def spectrum_quality(wave: np.ndarray, flux: np.ndarray, ivar: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    finite = np.isfinite(wave) & np.isfinite(flux)
    valid = finite & np.isfinite(ivar) & (ivar > 0) & (mask == 0)
    snr = flux[valid] * np.sqrt(ivar[valid])
    unique, counts = np.unique(mask, return_counts=True)
    return {"samples": int(wave.size), "wavelength_min_angstrom": float(np.nanmin(wave[finite])) if finite.any() else float("nan"), "wavelength_max_angstrom": float(np.nanmax(wave[finite])) if finite.any() else float("nan"), "nonfinite_wavelength_or_flux_count": int((~finite).sum()), "positive_ivar_fraction": float(np.mean(np.isfinite(ivar) & (ivar>0))), "mask_nonzero_fraction": float(np.mean(mask != 0)), "mask_value_counts": {str(int(k)):int(v) for k,v in zip(unique,counts)}, "valid_pixel_fraction": float(valid.mean()), "valid_pixel_count": int(valid.sum()), "snr_median": float(np.median(snr)) if snr.size else float("nan"), "snr_abs_p90": safe_quantile(np.abs(snr),.90), "flux_median_valid": float(np.median(flux[valid])) if valid.any() else float("nan"), "flux_mad_valid": robust_mad(flux[valid])}


def image_band_statistics(image: np.ndarray, bands: str) -> dict[str, dict[str, float | int]]:
    """Per-band pixel statistics; descriptive image evidence, not morphology labels."""
    names = list(bands) if len(bands) == image.shape[0] else [str(index) for index in range(image.shape[0])]
    result = {}
    for name, plane in zip(names, image):
        finite = plane[np.isfinite(plane)]
        result[name] = {"finite_pixels": int(finite.size), "invalid_fraction": float(1 - np.mean(np.isfinite(plane))), "median": float(np.median(finite)) if finite.size else float("nan"), "mad": robust_mad(finite), "p05": safe_quantile(finite,.05), "p95": safe_quantile(finite,.95)}
    return result


def _plot(dossier: dict[str, Any], wave: np.ndarray, flux: np.ndarray, model: np.ndarray, standard: np.ndarray, image: np.ndarray, destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3,1,figsize=(10,10))
    axes[0].plot(wave,flux,lw=.45,label="observed flux"); axes[0].plot(wave,model,lw=.45,label="available fitted model"); axes[0].set(title=f"DESI spectrum: {dossier['specid']}",ylabel="flux"); axes[0].legend(fontsize=8)
    axes[1].plot(wave,standard,lw=.4,color="#9b3a3a"); axes[1].axhline(5,color='grey',lw=.5); axes[1].axhline(-5,color='grey',lw=.5); axes[1].set(ylabel="standardized residual",xlabel="wavelength (Angstrom)")
    display=np.moveaxis(image,0,-1); low,high=np.nanpercentile(display,[1,99]); axes[2].imshow(np.clip((display-low)/(high-low if high>low else 1),0,1),origin="lower"); axes[2].set(title="Legacy Surveys DR10 grz cutout (display-stretched)",xticks=[],yticks=[])
    fig.tight_layout(); fig.savefig(destination,dpi=150); plt.close(fig)


def run(root: Path) -> dict[str, Any]:
    root=root.resolve(); result=root/'experiments/results'; evidence=result/'evidence'; dossiers=evidence/'dossiers'; plots=evidence/'plots'; dossiers.mkdir(parents=True,exist_ok=True)
    scores={row['specid']:row for row in csv.DictReader((result/'anomaly_scores.csv').open())}
    selected=[row for row in scores.values() if min(int(row['spectral_rank']),int(row['image_rank']),int(row['multimodal_rank']))<=20]
    manifest={row['specid']:row for row in (json.loads(line) for line in (root/'data/metadata/observations.jsonl').read_text().splitlines() if line)}
    output=[]
    for rank_row in sorted(selected,key=lambda x:min(int(x['spectral_rank']),int(x['image_rank']),int(x['multimodal_rank']))):
        sid=rank_row['specid']; source=manifest[sid]
        with np.load(root/source['spectrum_path']) as item:
            wave,flux,ivar,mask,model=(item[k] for k in ('wavelength','flux','ivar','mask','model'))
            quality=spectrum_quality(wave,flux,ivar,mask); discrepancy,residual,standard=residual_diagnostics(wave,flux,ivar,mask,model)
        with fits.open(root/source['image_path'],memmap=False) as hdus:
            image=hdus[0].data; bands=str(hdus[0].header.get('BANDS','grz')); image_quality=image_metrics(image)
        relationship=modality_relationship(int(rank_row['spectral_rank']),int(rank_row['image_rank']))
        plot_path=plots/f'{sid}.png'
        dossier={"specid":sid,"targetid":rank_row['targetid'],"coordinates":{"ra_deg":float(rank_row['ra_deg']),"dec_deg":float(rank_row['dec_deg'])},"redshift":float(rank_row['redshift']) if rank_row['redshift'] else None,"redshift_warning":{"value":int(rank_row['redshift_warning']),"flags":decode_zwarn(int(rank_row['redshift_warning']))},"phase_3_scores_and_ranks":{k:(float(rank_row[k]) if 'score' in k else int(rank_row[k])) for k in ('spectral_anomaly_score','spectral_rank','image_anomaly_score','image_rank','multimodal_anomaly_score','multimodal_rank')},"modality_relationship":relationship,"spectral_quality":quality,"model_discrepancy":discrepancy,"image_evidence":{"bands":bands,"per_band_statistics":image_band_statistics(image,bands),"quality_and_proxy_metrics":image_quality},"limitations":["Scores are Phase 3 relative baseline rankings, not probabilities or discoveries.","Fitted-model residuals are spectral model discrepancy diagnostics, not evidence of physical-model failure.","Image concentration, asymmetry, and S/N are simple proxies, not morphology classifications.","Legacy Survey image comparison is cross-survey consistency evidence, not independent confirmation."],"alternative_explanations":["low valid-pixel coverage or masking","limited spectral S/N or redshift-fit warning flags","image background/contrast differences or cutout context","baseline sensitivity to the small, GALAXY-only selection"],"recommended_follow_up":"Inspect the raw spectrum, mask locations, fitted-model assumptions, redshift-warning flags, and cutout context before any astrophysical interpretation.","plot":str(plot_path.relative_to(root))}
        _plot(dossier,wave,flux,model,standard,image,plot_path)
        (dossiers/f'{sid}.json').write_text(json.dumps(_safe(dossier),indent=2)+'\n')
        output.append({"specid":sid,"targetid":rank_row['targetid'],"spectral_rank":rank_row['spectral_rank'],"image_rank":rank_row['image_rank'],"multimodal_rank":rank_row['multimodal_rank'],"spectral_anomaly_score":rank_row['spectral_anomaly_score'],"image_anomaly_score":rank_row['image_anomaly_score'],"multimodal_anomaly_score":rank_row['multimodal_anomaly_score'],"modality_relationship":relationship,"zwarn_value":rank_row['redshift_warning'],"zwarn_flags":";".join(flag['name'] for flag in dossier['redshift_warning']['flags']),"valid_pixel_fraction":quality['valid_pixel_fraction'],"mask_nonzero_fraction":quality['mask_nonzero_fraction'],"snr_abs_p90":quality['snr_abs_p90'],"residual_abs_p99":discrepancy['standardized_residual_abs_p99'],"high_residual_pixels":discrepancy['high_standardized_residual_pixel_count'],"image_invalid_fraction":image_quality['image_invalid_fraction'],"image_snr_proxy_median":image_quality['image_snr_proxy_median'],"dossier_json":str((dossiers/f'{sid}.json').relative_to(root)),"plot":str(plot_path.relative_to(root))})
    with (evidence/'candidate_evidence.csv').open('w',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=sorted({k for r in output for k in r})); writer.writeheader(); writer.writerows(output)
    report={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"candidate_count":len(output),"selection":"deduplicated union of unchanged Phase 3 top-20 spectral, image, and multimodal rankings","zwarn_reference":"https://desidatamodel.readthedocs.io/en/latest/bitmasks.html#zwarn","dossiers":[r['specid'] for r in output]}
    (evidence/'evidence_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    relationship_counts={key:sum(r['modality_relationship']==key for r in output) for key in ('Spectral-dominated','Image-dominated','Both modalities unusual','Neither modality strongly unusual','Insufficient evidence')}
    lines=['# LIMEN Phase 4 evidence-interrogation summary','',f"- Investigation set: {len(output)} unique observations; deduplicated union of fixed Phase 3 top-20 lists.",'- No weighted priority score was calculated.','- Each dossier records original scores/ranks, quality context, ZWARN flags, mask-aware model discrepancy, a spectrum/model/residual plot, and the actual DR10 grz image preview.','', '## Modality relationship counts','',*[f'- {k}: {v}' for k,v in relationship_counts.items()],'','## Evidence limits','', '- Candidate categories are descriptive investigation categories, not scientific classifications.', '- Standardized residuals use only finite, unmasked pixels with positive inverse variance; they are model-discrepancy diagnostics, not physical-model failures.', '- The DESI ZWARN bitmask is decoded by individual bit using the official DESI data-model definitions.', '- The small GALAXY-only pilot and correlated survey selection preclude discovery or generalization claims.']
    (evidence/'evidence_summary.md').write_text('\n'.join(lines)+'\n'); return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]); args=parser.parse_args(); print(json.dumps(run(args.root),indent=2))
