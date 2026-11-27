"""Bounded background image work. Workers never touch widgets or the catalog."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from qtpy import QtCore

from spektrafilm_gui.library_store import RAW_EXTENSIONS


class TaskSignals(QtCore.QObject):
    finished = QtCore.Signal(object, object)
    failed = QtCore.Signal(object, str)


class Task(QtCore.QRunnable):
    def __init__(self, key, function):
        super().__init__()
        self.key, self.function = key, function
        self.signals = TaskSignals()

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            self.signals.failed.emit(self.key, str(exc))
        else:
            self.signals.finished.emit(self.key, result)


def thumbnail(path: str, cache: Path) -> str:
    source = Path(path)
    stat = source.stat()
    key = hashlib.sha256(f'{source}:{stat.st_mtime_ns}:{stat.st_size}:v2'.encode()).hexdigest()
    destination = cache / (key + '.jpg')
    if destination.exists():
        return str(destination)
    cache.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in RAW_EXTENSIONS:
        import rawpy
        with rawpy.imread(path) as raw:
            try:
                preview = raw.extract_thumb()
                image = (Image.open(BytesIO(preview.data)) if preview.format == rawpy.ThumbFormat.JPEG
                         else Image.fromarray(preview.data))
                image.load()
            except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
                image = Image.fromarray(raw.postprocess(half_size=True, use_camera_wb=True))
    else:
        try:
            with Image.open(path) as opened:
                opened.draft('RGB', (256, 192))
                image = ImageOps.exif_transpose(opened).copy()
        except (OSError, ValueError):
            from spektrafilm.utils.io import load_image_oiio
            pixels = load_image_oiio(path)[..., :3]
            image = Image.fromarray((np.clip(pixels, 0, 1) * 255).astype('uint8'))
    image = ImageOps.exif_transpose(image)
    image.thumbnail((256, 192))
    # A fixed-ratio canvas prevents Qt styles from stretching narrow/portrait icons.
    canvas = Image.new('RGB', (256, 192), (20, 20, 20))
    canvas.paste(image.convert('RGB'), ((256 - image.width) // 2, (192 - image.height) // 2))
    canvas.save(destination, 'JPEG', quality=85)
    return str(destination)


def decode_photo(path, state):
    if Path(path).suffix.lower() in RAW_EXTENSIONS:
        from spektrafilm.utils.raw_file_processor import load_and_process_raw_file
        raw = state.gui_only.load_raw
        return load_and_process_raw_file(
            path, white_balance=raw.white_balance, temperature=raw.temperature,
            tint=raw.tint, lens_correction=raw.lens_correction,
            output_colorspace=state.input_image.io.input_color_space,
            output_cctf_encoding=state.input_image.io.input_cctf_decoding)
    from spektrafilm.utils.io import load_image_oiio
    image = load_image_oiio(path)
    if image.ndim == 2:
        image = np.repeat(image[..., None], 3, axis=-1)
    if image.shape[-1] < 3:
        image = np.repeat(image[..., :1], 3, axis=-1)
    return image[..., :3]


def decode_live_photo(path, state):
    """Decode RAW bases once; slider movement never invokes LibRaw."""
    if Path(path).suffix.lower() not in RAW_EXTENSIONS:
        return decode_photo(path, state)
    from spektrafilm_gui.state import clone_gui_state
    base = clone_gui_state(state)
    base.gui_only.load_raw.white_balance = 'as_shot'
    shot = decode_photo(path, base)
    base.gui_only.load_raw.white_balance = 'daylight'
    daylight = decode_photo(path, base)
    from spektrafilm_gui.live_white_balance import fit_white_balance
    step = max(1, int(np.sqrt(shot.shape[0] * shot.shape[1] / 2048)))
    try:
        camera_balance = fit_white_balance(daylight[::step, ::step], shot[::step, ::step],
            state.input_image.io.input_color_space, state.input_image.io.input_cctf_decoding)
    except ValueError:
        camera_balance = None
    return {'as_shot': shot, 'daylight': daylight, 'camera_balance': camera_balance}
