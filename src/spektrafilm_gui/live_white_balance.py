"""Cached, linear-light white balance shared by preview and full-size scans."""
import colour
import numpy as np


def apply_white_balance(image, raw, colourspace, encoded):
    if raw.white_balance in ('as_shot', 'daylight'):
        return image
    temperature = 2850.0 if raw.white_balance == 'tungsten' else raw.temperature
    tint = 1.0 if raw.white_balance == 'tungsten' else raw.tint
    def white(kelvin):
        method = 'CIE Illuminant D Series' if kelvin >= 4000 else 'Kang 2002'
        return colour.xy_to_XYZ(colour.CCT_to_xy(np.float64(kelvin), method=method))
    space = colour.RGB_COLOURSPACES[colourspace]
    aces = colour.RGB_COLOURSPACES['ACES2065-1']
    adaptation = colour.adaptation.matrix_chromatic_adaptation_VonKries(white(temperature), white(6504.0))
    # Tint uses the original RAW processor's linear ACES green multiplier.
    tint_xyz = aces.matrix_RGB_to_XYZ @ np.diag([1.0, tint, 1.0]) @ aces.matrix_XYZ_to_RGB
    to_aces = colour.RGB_to_RGB(np.eye(3), space, aces).T
    from_aces = colour.RGB_to_RGB(np.eye(3), aces, space).T
    matrix = from_aces @ aces.matrix_XYZ_to_RGB @ tint_xyz @ adaptation @ aces.matrix_RGB_to_XYZ @ to_aces
    linear = space.cctf_decoding(image) if encoded else image
    adjusted = np.einsum('...j,ij->...i', linear, matrix)
    return np.asarray(space.cctf_encoding(adjusted) if encoded else adjusted, dtype=np.float32)


def fit_white_balance(source, target, colourspace, encoded):
    """Fit this editor's temperature/tint model to linear RGB sample pairs."""
    from scipy.optimize import least_squares
    from types import SimpleNamespace
    space = colour.RGB_COLOURSPACES[colourspace]
    source = np.asarray(source).reshape(-1, 3)
    target = np.asarray(target).reshape(-1, 3)
    if encoded:
        source, target = space.cctf_decoding(source), space.cctf_decoding(target)
    valid = (np.isfinite(source).all(axis=1) & np.isfinite(target).all(axis=1)
             & (source.min(axis=1) > .005) & (target.min(axis=1) > .005)
             & (source.max(axis=1) < .95) & (target.max(axis=1) < .95))
    source, target = source[valid], target[valid]
    if not len(source):
        raise ValueError('Choose a midtone neutral area, avoiding black and clipped highlights.')
    source, target = source[:2048], target[:2048]
    target = target / target.mean(axis=1, keepdims=True)
    def residual(values):
        raw = SimpleNamespace(white_balance='custom', temperature=values[0], tint=values[1])
        adjusted = apply_white_balance(source, raw, colourspace, False)
        return (adjusted / np.maximum(adjusted.mean(axis=1, keepdims=True), 1e-6) - target).ravel()
    result = least_squares(residual, [6504., 1.], bounds=([1000., .1], [25000., 3.]),
                           diff_step=.001, x_scale=[6500., 1.])
    return float(result.x[0]), float(result.x[1])
