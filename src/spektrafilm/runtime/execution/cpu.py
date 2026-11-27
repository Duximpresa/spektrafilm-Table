"""Reference adapter: preserve the existing numerical implementations."""

from spektrafilm.model.diffusion import apply_diffusion_filter_um
from spektrafilm.utils.gamut_compression import compress_rgb


class CpuBackend:
    def apply_diffusion(self, image, params, pixel_size_um):
        return apply_diffusion_filter_um(image, params, pixel_size_um)

    def compress_rgb(self, image, spec, *, output_color_space=None):
        return compress_rgb(image, spec, output_color_space=output_color_space)

    def begin_run(self):
        pass

    def end_run(self):
        pass

    def status(self):
        return "CPU"

    def close(self):
        pass
