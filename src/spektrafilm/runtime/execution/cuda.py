"""Lazy NVIDIA implementation. Host arrays and stochastic stages stay on CPU.

Each backend owns its allocator; GPU calls are serialized across simulators.
No global allocator, device reset, monkeypatch, or experimental bootstrap is used.
"""

import logging
from contextlib import contextmanager
from threading import RLock

import numpy as np

from .cpu import CpuBackend

_GPU_LOCK = RLock()
log = logging.getLogger(__name__)


class BackendUnavailable(RuntimeError):
    pass


class CudaBackend(CpuBackend):
    def __init__(self, options):
        self.options = options
        self.cp = None
        self.pool = None
        self.stream = None
        self.unavailable = None
        self.device_name = "NVIDIA CUDA"
        self.begin_run()

    def begin_run(self):
        self.gpu_calls = 0
        self.fallbacks = []

    def _initialize(self):
        if self.unavailable:
            raise BackendUnavailable(self.unavailable)
        if self.cp is not None:
            return
        try:
            import cupy as cp
            from cupy.cuda.compiler import CompileException

            self._compile_error = CompileException

            with cp.cuda.Device(self.options.device_id):
                self.pool = cp.cuda.MemoryPool()
                free, _ = cp.cuda.runtime.memGetInfo()
                self.pool.set_limit(size=int(min(6_000_000_000, free * 0.7)))
                self.stream = cp.cuda.Stream(non_blocking=True)
                with cp.cuda.using_allocator(self.pool.malloc), self.stream:
                    # Exercise transfer, compilation, FP64 math and cuFFT.
                    try:
                        probe = cp.arange(16, dtype=cp.float64).reshape(4, 4)
                        result = cp.asnumpy(
                            cp.fft.irfftn(cp.fft.rfftn(probe + 1), s=(4, 4))
                        )
                    except CompileException as exc:
                        raise BackendUnavailable(
                            f"CUDA probe compilation failed: {exc}"
                        ) from exc
                    if not np.allclose(result, np.arange(16).reshape(4, 4) + 1):
                        raise BackendUnavailable("CUDA numerical probe failed")
                props = cp.cuda.runtime.getDeviceProperties(self.options.device_id)
                name = props["name"]
                self.device_name = (
                    name.decode() if isinstance(name, bytes) else str(name)
                )
            self.cp = cp
        except (ImportError, OSError, RuntimeError, MemoryError) as exc:
            self.unavailable = f"CUDA unavailable: {exc}. Install the project's [cuda] extra and a compatible NVIDIA driver."
            self.pool = None
            self.stream = None
            raise BackendUnavailable(self.unavailable) from exc

    @contextmanager
    def _scope(self):
        cp = self.cp
        with cp.cuda.Device(self.options.device_id):
            cache = cp.fft.config.get_plan_cache()
            previous_size = cache.get_size()
            cache.set_size(0)
            try:
                with cp.cuda.using_allocator(self.pool.malloc), self.stream:
                    yield
                    self.stream.synchronize()
            finally:
                cache.set_size(previous_size)

    def _fallback(self, label, reason, cpu_call):
        if not self.options.allow_fallback:
            raise BackendUnavailable(f"{label}: {reason}")
        message = f"{label}: {reason}"
        if message not in self.fallbacks:
            self.fallbacks.append(message)
            log.warning("CPU fallback — %s", message)
        return cpu_call()

    def _run(self, label, gpu_call, cpu_call):
        with _GPU_LOCK:
            try:
                self._initialize()
            except BackendUnavailable as exc:
                return self._fallback(label, str(exc), cpu_call)
            try:
                with self._scope():
                    result = gpu_call()
                self.gpu_calls += 1
                return result
            except self.cp.cuda.memory.OutOfMemoryError:
                # The deterministic input is still intact; do not replay RNG stages.
                self.pool.free_all_blocks()
                return self._fallback(label, "insufficient GPU memory", cpu_call)
            except self.cp.cuda.runtime.CUDARuntimeError as exc:
                self.unavailable = f"CUDA device error: {exc}"
                return self._fallback(label, self.unavailable, cpu_call)
            except self.cp.cuda.cufft.CuFFTError as exc:
                # cuFFT allocation/setup errors are recoverable at this operator.
                return self._fallback(label, f"CUDA FFT error: {exc}", cpu_call)
            except self._compile_error as exc:
                raise BackendUnavailable(
                    f"CUDA kernel compilation failed: {exc}"
                ) from exc

    def apply_diffusion(self, image, params, pixel_size_um):
        cpu_call = lambda: super(CudaBackend, self).apply_diffusion(
            image, params, pixel_size_um
        )
        if not params.active or params.strength <= 0 or params.spatial_scale <= 0:
            return cpu_call()

        def gpu_call():
            from .cuda_kernels import DiffusionGPU

            return DiffusionGPU(params, pixel_size_um, image.shape).host(image)

        return self._run("Diffusion", gpu_call, cpu_call)

    def compress_rgb(self, image, spec, *, output_color_space=None):
        cpu_call = lambda: super(CudaBackend, self).compress_rgb(
            image, spec, output_color_space=output_color_space
        )
        if spec.algorithm == "off":
            return cpu_call()
        if spec.algorithm != "cam16ucs":
            # Supported CPU algorithms are intentional hybrid execution, not failure.
            self.fallbacks.append(f"{spec.algorithm}: CPU implementation")
            return cpu_call()
        if output_color_space is None:
            return cpu_call()  # Preserve the reference validation error.

        def gpu_call():
            from .cuda_kernels import GamutGPU

            rows = self.options.tile_rows
            while True:
                try:
                    return GamutGPU(spec, output_color_space, tile_rows=rows).host(
                        image
                    )
                except self.cp.cuda.memory.OutOfMemoryError:
                    if rows == 1:
                        raise
                    self.pool.free_all_blocks()
                    rows = max(1, rows // 2)

        return self._run("CAM16-UCS", gpu_call, cpu_call)

    def status(self):
        actual = (
            f"CUDA float64 · {self.device_name} + CPU"
            if self.gpu_calls
            else "CPU (no CUDA operations)"
        )
        if self.fallbacks:
            actual = (
                "CPU fallback · "
                + actual
                + " · "
                + "; ".join(dict.fromkeys(self.fallbacks))
            )
        return actual

    def end_run(self):
        # No image/PSF cache survives a request; pool growth is bounded even when
        # Qt schedules the next request on a different worker thread.
        with _GPU_LOCK:
            if self.pool is not None and self.cp is not None:
                try:
                    with self.cp.cuda.Device(self.options.device_id):
                        self.pool.free_all_blocks()
                except self.cp.cuda.runtime.CUDARuntimeError as exc:
                    self.unavailable = f"CUDA cleanup failed: {exc}"
                    log.warning(self.unavailable)

    def close(self):
        self.end_run()
