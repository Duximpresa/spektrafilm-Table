"""Backend contracts and optional real-CUDA numerical regression.
Run GPU tests explicitly with SPEKTRAFILM_TEST_CUDA=1; failures are not skipped.
"""

import builtins
import os
import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest

from spektrafilm.model.diffusion import (
    DIFFUSION_FILTER_FAMILIES,
    apply_diffusion_filter_um,
)
from spektrafilm.runtime.execution import ExecutionOptions, create_backend
from spektrafilm.runtime.execution.cuda import BackendUnavailable
from spektrafilm.runtime.params_schema import DiffusionFilterParams
from spektrafilm.runtime.process import Simulator
from spektrafilm.utils.gamut_compression import OutputGamutCompressSpec, compress_rgb


def test_cpu_does_not_import_cuda():
    code = "from spektrafilm.runtime.execution import create_backend; b=create_backend(); import sys; assert 'cupy' not in sys.modules; assert b.status() == 'CPU'"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_missing_cuda_fallback_and_strict(monkeypatch):
    original = builtins.__import__

    def no_cuda(name, *args, **kwargs):
        if name == "cupy":
            raise ImportError("CUDA test dependency missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_cuda)
    image = np.ones((4, 5, 3)) * 0.2
    params = DiffusionFilterParams(active=True)
    backend = create_backend(ExecutionOptions(backend="cuda"))
    actual = backend.apply_diffusion(image, params, 5)
    np.testing.assert_array_equal(actual, apply_diffusion_filter_um(image, params, 5))
    assert "CUDA test dependency missing" in backend.status()
    assert backend.gpu_calls == 0
    strict = create_backend(ExecutionOptions(backend="cuda", allow_fallback=False))
    with pytest.raises(BackendUnavailable):
        strict.apply_diffusion(image, params, 5)


def test_update_keeps_execution_backend(default_params):
    simulator = Simulator(default_params, execution=ExecutionOptions())
    backend = simulator._pipeline.backend
    simulator.update_params(default_params)
    assert simulator._pipeline.backend is backend
    assert simulator._pipeline._filming_stage._backend is backend
    assert simulator._pipeline._printing_stage._backend is backend
    assert simulator._pipeline._scanning_stage._backend is backend


@pytest.fixture
def cuda_backend():
    if os.environ.get("SPEKTRAFILM_TEST_CUDA") != "1":
        pytest.skip("set SPEKTRAFILM_TEST_CUDA=1 to require an actual CUDA device")
    backend = create_backend(
        ExecutionOptions(backend="cuda", allow_fallback=False, tile_rows=3)
    )
    backend._initialize()
    yield backend
    backend.close()
    assert backend.pool.total_bytes() == 0


@pytest.mark.parametrize("color_space", ["sRGB", "Display P3", "ProPhoto RGB"])
@pytest.mark.parametrize("lightness", [None, (0.75, 1.0, 2.0)])
def test_cuda_gamut_negative_hdr_noncontiguous(cuda_backend, color_space, lightness):
    rng = np.random.default_rng(72)
    image = rng.uniform(-0.05, 3, (17, 23, 3))[:, ::2]
    image[0, :5] = [[0, 0, 0], [1, 1, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1]]
    spec = OutputGamutCompressSpec(lightness_compression=lightness)
    expected = compress_rgb(image, spec, output_color_space=color_space)
    actual = cuda_backend.compress_rgb(image, spec, output_color_space=color_space)
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-10)
    assert cuda_backend.gpu_calls == 1


@pytest.mark.parametrize("shape", [(1, 1, 3), (16, 18, 3), (17, 19, 3)])
@pytest.mark.parametrize("family", DIFFUSION_FILTER_FAMILIES)
def test_cuda_diffusion_boundaries(cuda_backend, shape, family):
    image = np.zeros(shape)
    image[0, 0] = [1, 2, 3]
    image[-1, -1] = [2, 1, 3]
    image[shape[0] // 2, shape[1] // 2] = [3, 2, 1]
    params = DiffusionFilterParams(
        active=True,
        filter_family=family,
        halo_warmth=0.7,
        bloom_size=1.3,
        core_intensity=0.8,
        spatial_scale=0.6,
    )
    expected = apply_diffusion_filter_um(image, params, 4.5)
    actual = cuda_backend.apply_diffusion(image, params, 4.5)
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-10)
    assert cuda_backend.gpu_calls == 1


def test_cuda_oom_fallback_is_local(cuda_backend):
    cuda_backend.options = replace(cuda_backend.options, allow_fallback=True)
    image = np.arange(12.0).reshape(2, 2, 3)
    original = image.copy()

    def fail():
        raise cuda_backend.cp.cuda.memory.OutOfMemoryError(100, 0, 50)

    actual = cuda_backend._run("test", fail, lambda: image * 2)
    np.testing.assert_array_equal(image, original)
    np.testing.assert_array_equal(actual, original * 2)
    assert "insufficient GPU memory" in cuda_backend.status()
    with pytest.raises(ValueError, match="algorithm defect"):
        cuda_backend._run(
            "test",
            lambda: (_ for _ in ()).throw(ValueError("algorithm defect")),
            lambda: image,
        )


def test_cuda_complete_pipeline_and_update(
    cuda_backend, default_params, small_rgb_image
):
    params = default_params
    params.camera.diffusion_filter.active = True
    params.enlarger.diffusion_filter.active = True
    cpu = Simulator(params)
    gpu = Simulator(params, execution=cuda_backend.options)
    for scan_film in (False, True):
        params.io.scan_film = scan_film
        cpu.update_params(params)
        gpu.update_params(params)
        expected = cpu.process(small_rgb_image)
        actual = gpu.process(small_rgb_image)
        np.testing.assert_allclose(actual, expected, atol=1e-9, rtol=1e-9)
        assert gpu._pipeline.backend.gpu_calls == (2 if scan_film else 3)
        assert "CUDA float64" in gpu.execution_status()
    gpu.close()


def test_cuda_gamut_retries_smaller_tiles(cuda_backend, monkeypatch):
    from spektrafilm.runtime.execution import cuda_kernels

    original = cuda_kernels.GamutGPU
    attempts = []

    class LimitedGamut(original):
        def host(self, image):
            attempts.append(self.tile_rows)
            if self.tile_rows > 1:
                raise cuda_backend.cp.cuda.memory.OutOfMemoryError(100, 0, 50)
            return super().host(image)

    monkeypatch.setattr(cuda_kernels, "GamutGPU", LimitedGamut)
    image = np.full((7, 5, 3), 0.18)
    spec = OutputGamutCompressSpec()
    expected = compress_rgb(image, spec, output_color_space="sRGB")
    actual = cuda_backend.compress_rgb(image, spec, output_color_space="sRGB")
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-10)
    assert attempts == [3, 1]
    assert cuda_backend.gpu_calls == 1
    assert not cuda_backend.fallbacks


def test_cuda_device_failure_disables_later_dispatch(cuda_backend):
    cuda_backend.options = replace(cuda_backend.options, allow_fallback=True)

    def fail():
        raise cuda_backend.cp.cuda.runtime.CUDARuntimeError(30)

    assert cuda_backend._run("first", fail, lambda: 7) == 7
    cuda_backend.begin_run()
    assert (
        cuda_backend._run("next", lambda: pytest.fail("must not dispatch"), lambda: 8)
        == 8
    )
    assert "CUDA device error" in cuda_backend.status()
