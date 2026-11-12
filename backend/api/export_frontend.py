"""Create lightweight, derived candidate assets for the local frontend.

This exports decimated display data and rendered PNG previews only. It never
changes raw NPZ/FITS inputs or experiment outputs used by Phases 1–6.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from astropy.io import fits
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _safe(values: np.ndarray) -> list[float | None]:
    return [float(item) if np.isfinite(item) else None for item in values]


def run(root: Path) -> None:
    root=root.resolve(); output=root/'experiments/results/frontend/candidates'; output.mkdir(parents=True,exist_ok=True)
    manifest={row['specid']:row for row in (json.loads(line) for line in (root/'data/metadata/observations.jsonl').read_text().splitlines() if line)}
    for dossier_path in (root/'experiments/results/triage/dossiers').glob('*.json'):
        triage=json.loads(dossier_path.read_text()); candidate=triage['candidate']; sid=candidate['specid']; source=manifest[sid]
        with np.load(root/source['spectrum_path']) as raw:
            wave,flux,ivar,mask,model=(raw[key] for key in ('wavelength','flux','ivar','mask','model'))
            valid=np.isfinite(wave)&np.isfinite(flux)&np.isfinite(ivar)&(ivar>0)&(mask==0)&np.isfinite(model)
            residual=np.full(wave.size,np.nan); residual[valid]=(flux[valid]-model[valid])*np.sqrt(ivar[valid])
            indices=np.linspace(0,wave.size-1,600,dtype=int)
            payload={"specid":sid,"wavelength_angstrom":_safe(wave[indices]),"flux":_safe(flux[indices]),"model_flux":_safe(model[indices]),"standardized_residual":_safe(residual[indices]),"masked":(mask[indices]!=0).tolist()}
            (output/f'{sid}.json').write_text(json.dumps(payload,separators=(',',':')))
        with fits.open(root/source['image_path'],memmap=False) as hdus:
            image=np.moveaxis(hdus[0].data,0,-1); low,high=np.nanpercentile(image,[1,99]); display=np.clip((image-low)/(high-low if high>low else 1),0,1)
            fig,ax=plt.subplots(figsize=(4,4),dpi=120); ax.imshow(display,origin='lower'); ax.set_axis_off(); fig.subplots_adjust(0,0,1,1); fig.savefig(output/f'{sid}.png',transparent=False); plt.close(fig)


if __name__=='__main__': run(Path(__file__).resolve().parents[2])
