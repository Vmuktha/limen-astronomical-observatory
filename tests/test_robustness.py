import numpy as np

from experiments.robustness.perturbations import (blur_image, contiguous_spectral_mask,
    degrade_image_noise, degrade_spectrum_noise, mask_image_block, reduced_spectral_coverage)


def test_spectral_noise_is_reproducible_preserves_masked_pixels_and_updates_ivar():
    flux=np.array([1.,2.,3.]); ivar=np.array([4.,4.,4.]); mask=np.array([0,1,0]); original=flux.copy()
    first,new_ivar=degrade_spectrum_noise(flux,ivar,mask,2.,np.random.default_rng(7)); second,_=degrade_spectrum_noise(flux,ivar,mask,2.,np.random.default_rng(7))
    assert np.array_equal(first,second)
    assert first[1]==original[1] and new_ivar[1]==ivar[1]
    assert np.allclose(new_ivar[[0,2]],1.)
    assert np.array_equal(flux,original)


def test_contiguous_mask_and_reduced_coverage_do_not_mutate_source():
    wave=np.arange(10.); mask=np.zeros(10,dtype=int); changed,info=contiguous_spectral_mask(wave,mask,.3,np.random.default_rng(2))
    assert mask.sum()==0 and changed.sum()==3 and info['fraction']==.3
    result=reduced_spectral_coverage(wave,(wave,mask),.2,'red')
    assert len(result[0])==8 and len(wave)==10


def test_image_degradations_are_reproducible_and_do_not_mutate_raw_array():
    image=np.ones((3,8,8)); image[:,0,:]=0.; original=image.copy()
    first=degrade_image_noise(image,1.,np.random.default_rng(9)); second=degrade_image_noise(image,1.,np.random.default_rng(9))
    assert np.array_equal(first,second) and np.array_equal(image,original)
    blurred=blur_image(image,1.); masked,block=mask_image_block(image,.25,np.random.default_rng(2))
    assert blurred.shape==image.shape and np.isnan(masked).any() and block['width']==4
