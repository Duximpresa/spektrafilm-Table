"""Execution backends, independent of photo parameters and GUI libraries.

Add a backend descriptor and a lazy factory here to support another platform.
Importing this module (including CPU-only use) never imports a GPU library.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BackendInfo:
    id: str
    label: str


BACKENDS = (
    BackendInfo("cpu", "CPU"),
    BackendInfo("cuda", "NVIDIA CUDA (GPU, float64)"),
)


@dataclass(frozen=True)
class ExecutionOptions:
    backend: str = "cpu"
    device_id: int = 0
    allow_fallback: bool = True
    tile_rows: int = 128

    def __post_init__(self):
        if self.backend not in {item.id for item in BACKENDS}:
            raise ValueError(f"Unknown execution backend: {self.backend}")
        if self.device_id < 0 or self.tile_rows < 1:
            raise ValueError("device_id must be non-negative and tile_rows positive")


class ExecutionBackend(Protocol):
    def apply_diffusion(self, image, params, pixel_size_um): ...
    def compress_rgb(self, image, spec, *, output_color_space=None): ...
    def begin_run(self): ...
    def end_run(self): ...
    def status(self) -> str: ...
    def close(self): ...


def create_backend(options=None) -> ExecutionBackend:
    options = options or ExecutionOptions()
    if options.backend == "cuda":
        from .cuda import CudaBackend

        return CudaBackend(options)
    from .cpu import CpuBackend

    return CpuBackend()
