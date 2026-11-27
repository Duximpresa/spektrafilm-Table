"""Float64 CUDA kernels for the runtime execution backend.
CAM16 equations follow the installed colour-science (BSD-3-Clause) implementation.
Compression and diffusion follow this project's GPL-3.0 implementation.

CAM16 port attribution and license:
Copyright 2013 Colour Developers

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE

"""

import colour
import cupy as cp
import numpy as np
from colour.appearance.cam16 import MATRIX_16, MATRIX_INVERSE_16
from colour.appearance.ciecam02 import (
    achromatic_response_forward,
    degree_of_adaptation,
    post_adaptation_non_linear_response_compression_forward,
    viewing_conditions_dependent_parameters,
)

from spektrafilm.model import diffusion as df
from spektrafilm.utils import gamut_compression as gc


def spow(x, p):
    return cp.sign(x) * cp.abs(x) ** p


def knee(d, params):
    threshold, limit, power = params
    scale = limit - threshold
    x = cp.maximum((d - threshold) / scale, 0)
    small = x / (1 + cp.minimum(x, 1) ** power) ** (1 / power)
    large = (1 + (1 / cp.maximum(x, 1)) ** power) ** (-1 / power)
    y = cp.where(x > 1, large, small)
    return cp.where(d > threshold, threshold + scale * y, d)


def mat(x, m):
    return cp.stack(
        [
            x[..., 0] * m[i, 0] + x[..., 1] * m[i, 1] + x[..., 2] * m[i, 2]
            for i in range(3)
        ],
        axis=-1,
    )


class GamutGPU:
    def __init__(self, spec, color_space="sRGB", dtype=np.float64, tile_rows=128):
        self.spec = spec
        self.dtype = np.dtype(dtype)
        self.tile_rows = tile_rows
        cs = colour.RGB_COLOURSPACES[color_space]
        white = gc._output_cs_whitepoint_xyz(color_space) * 100
        n, fl, nbb, ncb, z = viewing_conditions_dependent_parameters(
            20.0, white[1], 64.0
        )
        d = np.clip(degree_of_adaptation(1.0, 64.0), 0, 1)
        drgb = d * white[1] / (MATRIX_16 @ white) + 1 - d
        aw = achromatic_response_forward(
            post_adaptation_non_linear_response_compression_forward(
                drgb * (MATRIX_16 @ white), fl
            ),
            nbb,
        )
        self.fl = float(fl)
        self.nbb = float(nbb)
        self.ncb = float(ncb)
        self.z = float(z)
        self.aw = float(aw)
        self.chroma_factor = float((1.64 - 0.29**n) ** 0.73)
        self.drgb = cp.asarray(drgb, dtype=dtype)
        self.to_xyz = cp.asarray(cs.matrix_RGB_to_XYZ, dtype=dtype)
        self.to_rgb = cp.asarray(cs.matrix_XYZ_to_RGB, dtype=dtype)
        self.cat = cp.asarray(MATRIX_16, dtype=dtype)
        self.invcat = cp.asarray(MATRIX_INVERSE_16, dtype=dtype)
        lg, hg, tab = gc._get_output_c_max_table("cam16ucs", color_space)
        self.l0 = float(lg[0])
        self.l1 = float(lg[-1])
        self.h0 = float(hg[0])
        self.hs = float(hg[1] - hg[0])
        self.nl = len(lg)
        self.nh = len(hg)
        self.table = cp.asarray(tab, dtype=dtype)
        self.white_jp = gc._cam16ucs_white_Jp(color_space)

    def lookup(self, L, h):
        L = cp.clip(L, self.l0, self.l1)
        hi = (h - self.h0) / self.hs
        hf = cp.floor(hi)
        h0 = hf.astype(cp.int64) % self.nh
        h1 = (h0 + 1) % self.nh
        dh = hi - hf
        li = (L - self.l0) / (self.l1 - self.l0) * (self.nl - 1)
        l0 = cp.clip(cp.floor(li).astype(cp.int64), 0, self.nl - 2)
        l1 = l0 + 1
        dl = li - l0
        return (
            self.table[l0, h0] * (1 - dl) * (1 - dh)
            + self.table[l0, h1] * (1 - dl) * dh
            + self.table[l1, h0] * dl * (1 - dh)
            + self.table[l1, h1] * dl * dh
        )

    def tile(self, rgb):
        xyz = mat(rgb, self.to_xyz) * 100
        rgbc = mat(xyz, self.cat) * self.drgb
        v = (self.fl * cp.abs(rgbc) / 100) ** 0.42
        ra = 400 * cp.sign(rgbc) * v / (27.13 + v) + 0.1
        R, G, B = (ra[..., 0], ra[..., 1], ra[..., 2])
        a = R - 12 * G / 11 + B / 11
        b = (R + G - 2 * B) / 9
        h = cp.arctan2(b, a)
        et = (cp.cos(h + 2) + 3.8) / 4
        A = (2 * R + G + B / 20 - 0.305) * self.nbb
        J = 100 * spow(A / self.aw, 0.69 * self.z)
        denom = R + G + 21 * B / 20
        t = (
            50000
            / 13
            * self.ncb
            * et
            * cp.sqrt(a * a + b * b)
            / cp.where(denom == 0, 1, denom)
        )
        t = cp.where(denom == 0, 0, t)
        C = spow(t, 0.9) * spow(J / 100, 0.5) * self.chroma_factor
        M = C * self.fl**0.25
        jp = 1.7 * J / (1 + 0.007 * J)
        mp = cp.log1p(0.0228 * M) / 0.0228
        ap = mp * cp.cos(h)
        bp = mp * cp.sin(h)
        if self.spec.lightness_compression is not None:
            jp = (
                knee(jp / self.white_jp, self.spec.lightness_compression)
                * self.white_jp
            )
        chroma = cp.hypot(ap, bp)
        hp = cp.arctan2(bp, ap)
        cmax = cp.fmax(self.lookup(jp, hp), 1e-09)
        chroma = knee(chroma / cmax, self.spec.knee) * cmax
        J = jp / (1.7 - 0.007 * jp)
        M = cp.expm1(0.0228 * chroma) / 0.0228
        C = M / self.fl**0.25
        t = spow(
            C
            / (cp.sqrt(cp.maximum(J, np.finfo(float).eps) / 100) * self.chroma_factor),
            1 / 0.9,
        )
        et = (cp.cos(hp + 2) + 3.8) / 4
        A = self.aw * spow(J / 100, 1 / (0.69 * self.z))
        p1 = cp.where(t != 0, 50000 / 13 * self.ncb * et / cp.where(t != 0, t, 1), 0)
        p2 = A / self.nbb + 0.305
        gamma = (
            p2
            * 3.05
            * (460 / 1403)
            / (
                p1
                + 3.05 * (220 / 1403) * cp.cos(hp)
                + (-27 + 1.05 * 6300) / 1403 * cp.sin(hp)
            )
        )
        a = cp.where(t == 0, 0, gamma * cp.cos(hp))
        b = cp.where(t == 0, 0, gamma * cp.sin(hp))
        # colour's quadrant-based inverse initializes a/b to zero and leaves
        # them there when hue is NaN (neither comparison selects a quadrant).
        # Preserve that behavior for e.g. ProPhoto blue with negative CAM J.
        a = cp.where(cp.isnan(hp), 0, a)
        b = cp.where(cp.isnan(hp), 0, b)
        ra = cp.stack(
            [
                (460 * p2 + 451 * a + 288 * b) / 1403,
                (460 * p2 - 891 * a - 261 * b) / 1403,
                (460 * p2 - 220 * a - 6300 * b) / 1403,
            ],
            axis=-1,
        )
        q = ra - 0.1
        rgbc = (
            cp.sign(q)
            * 100
            / self.fl
            * spow(27.13 * cp.abs(q) / (400 - cp.abs(q)), 1 / 0.42)
        )
        xyz = mat(rgbc / self.drgb, self.invcat) / 100
        return mat(xyz, self.to_rgb)

    def device(self, image):
        out = cp.empty_like(image)
        for start in range(0, image.shape[0], self.tile_rows):
            out[start : start + self.tile_rows] = self.tile(
                image[start : start + self.tile_rows]
            )
        return out

    def host(self, image):
        # Host streaming bounds VRAM independently of the total image height.
        image = np.asarray(image, dtype=np.float64)
        if image.ndim == 0 or image.shape[-1] != 3:
            raise ValueError("Expected RGB input with shape (..., 3)")
        flat = image.reshape(-1, 3)
        result = np.empty_like(flat)
        width = image.shape[-2] if image.ndim > 1 else 1
        count = max(1, self.tile_rows * width)
        for start in range(0, len(flat), count):
            result[start : start + count] = cp.asnumpy(
                self.tile(cp.asarray(flat[start : start + count]))
            )
        return result.reshape(image.shape)


class DiffusionGPU:
    def __init__(self, params, pixel_size_um, shape, dtype=np.float64):
        self.dtype = np.dtype(dtype)
        self.params = params
        family = params.filter_family
        overrides = df._overrides_from_params(params)
        radius = int(
            np.ceil(
                max(
                    8
                    * df._bloom_max_lambda_um(family, overrides)
                    * params.spatial_scale
                    / pixel_size_um,
                    5,
                )
            )
        )
        self.radius = min(radius, max(min(shape[:2]) // 2 - 1, 1))
        psf = df.diffusion_filter_psf(
            (2 * self.radius + 1, 2 * self.radius + 1),
            family=family,
            spatial_scale=params.spatial_scale,
            pixel_size_um=pixel_size_um,
            halo_warmth=params.halo_warmth,
            overrides=overrides,
        )
        self.psf = cp.asarray(psf, dtype=dtype)
        self.fraction = df._strength_to_scatter(params.strength, family)

    def device(self, image):
        from scipy.fft import next_fast_len

        r = self.radius
        out = cp.empty_like(image)
        for ch in range(3):
            padded = cp.pad(image[..., ch], ((r, r), (r, r)), mode="reflect")
            shape = tuple(padded.shape[i] + self.psf.shape[i] - 1 for i in range(2))
            fshape = tuple(next_fast_len(n, real=True) for n in shape)
            ft = cp.fft.rfftn(padded, s=fshape) * cp.fft.rfftn(
                self.psf[..., ch], s=fshape
            )
            conv = cp.fft.irfftn(ft, s=fshape)[: shape[0], : shape[1]]
            blurred = conv[r : r + padded.shape[0], r : r + padded.shape[1]]
            out[..., ch] = (1 - self.fraction) * image[
                ..., ch
            ] + self.fraction * blurred[r:-r, r:-r]
            del padded, blurred, ft, conv
        return out

    def host(self, image):
        dev = cp.asarray(image, dtype=self.dtype)
        out = self.device(dev)
        return cp.asnumpy(out).astype(np.float64, copy=False)
