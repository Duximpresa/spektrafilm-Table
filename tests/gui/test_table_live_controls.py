from types import SimpleNamespace
from pathlib import Path

import colour
import numpy as np
from qtpy import QtCore, QtWidgets as W

from spektrafilm_gui.import_preview import ImportPreview
from spektrafilm_gui.controller import GuiController, INPUT_LAYER_NAME, INPUT_PREVIEW_LAYER_NAME
from spektrafilm_gui.live_white_balance import apply_white_balance
from spektrafilm_gui.state_bridge import collect_gui_state
from .test_library import library, pump_until
from .test_table_workspace import make_photo


def test_multiple_folders_recursion_preview_and_restore(library, tmp_path, monkeypatch):
    a = make_photo(tmp_path / 'a' / 'one.jpg')
    b = make_photo(tmp_path / 'b' / 'two.jpg')
    nested = make_photo(tmp_path / 'a' / 'sub' / 'three.jpg')
    calls = []
    monkeypatch.setattr('spektrafilm_gui.import_preview.thumbnail', lambda *args: calls.append(args))
    dialog = ImportPreview(library, existing_paths=[], cache=library.cache)
    dialog.preview_enabled.setChecked(False)
    dialog.recursive.setChecked(False)
    for folder in (a.parent, b.parent):
        index = dialog.file_model.index(str(folder))
        dialog.tree.selectionModel().select(index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
    pump_until(lambda: not dialog.tasks and not dialog.scanning)
    assert set(dialog.checked_paths()) == {str(a), str(b)}
    assert not calls
    dialog.recursive.setChecked(True)
    pump_until(lambda: not dialog.tasks and not dialog.scanning)
    assert set(dialog.checked_paths()) == {str(a), str(b), str(nested)}
    dialog.reject()
    restored = ImportPreview(library, existing_paths=[], cache=library.cache)
    pump_until(lambda: not restored.tasks and not restored.scanning)
    assert {Path(path) for path in restored.sources} == {a.parent, b.parent}
    assert not restored.preview_enabled.isChecked()
    assert restored.recursive.isChecked()
    restored.reject()


def test_file_dialog_remembers_directory(library, tmp_path, monkeypatch):
    path = make_photo(tmp_path / 'photos' / 'one.jpg')
    starts = []
    def choose(parent, title, directory, filters):
        starts.append(directory)
        return [str(path)], ''
    monkeypatch.setattr(W.QFileDialog, 'getOpenFileNames', choose)
    monkeypatch.setattr(library, 'show_import_preview', lambda paths: None)
    library.choose_files()
    library.choose_files()
    assert starts == ['', str(path.parent)]


def test_white_balance_matches_raw_processor_in_encoded_space():
    from spektrafilm.utils.raw_file_processor import (
        _apply_white_balance_adaptation, _apply_tint_adjustment, _whitepoint_xyz_from_temperature)
    image = np.random.default_rng(7).uniform(.1, .6, (5, 7, 3)).astype('float32')
    expected = _apply_white_balance_adaptation(image, _whitepoint_xyz_from_temperature(4300),
                                             _whitepoint_xyz_from_temperature(6504))
    expected = _apply_tint_adjustment(expected, 1.13)
    expected = colour.RGB_to_RGB(expected, 'ACES2065-1', 'sRGB', apply_cctf_encoding=True)
    encoded = colour.RGB_to_RGB(image, 'ACES2065-1', 'sRGB', apply_cctf_encoding=True)
    raw = SimpleNamespace(white_balance='custom', temperature=4300, tint=1.13)
    actual = apply_white_balance(encoded, raw, 'sRGB', True)
    np.testing.assert_allclose(actual, expected, atol=2e-4)


def test_live_slider_uses_cache_and_scan_full_resolution(library, monkeypatch):
    controller = library.controller
    image = np.full((48, 64, 3), .25, dtype='float32')
    controller._current_input_image = image
    controller._daylight_image = image.copy()
    controller.preview_divisor = 4
    monkeypatch.setattr(controller, 'refresh_preview_cache', lambda: setattr(controller, '_current_preview_image',
        controller._resize_for_preview(image, max_size=1024)))
    runs = []
    monkeypatch.setattr(controller, 'run_preview', lambda: runs.append(True))
    library.widgets.load_raw.temperature_slider.setValue(4200)
    pump_until(lambda: bool(runs))
    assert library.widgets.load_raw.white_balance.value == 'custom'
    assert controller._current_preview_image.shape == (12, 16, 3)
    assert not np.allclose(controller._current_preview_image, .25)
    cached = controller._base_preview_cache[1]
    library.widgets.load_raw.tint_slider.setValue(115)
    controller._wb_timer.stop()
    controller._update_white_balance()
    assert controller._base_preview_cache[1] is cached
    full = controller._simulation_input_image(source_layer_name=INPUT_LAYER_NAME)
    preview = controller._simulation_input_image(source_layer_name=INPUT_PREVIEW_LAYER_NAME)
    assert full.shape == image.shape
    np.testing.assert_allclose(full[0, 0], preview[0, 0], atol=1e-6)
    np.testing.assert_array_equal(image, np.full_like(image, .25))
    state = collect_gui_state(widgets=library.widgets)
    assert state.gui_only.load_raw.temperature == 4200
    assert state.gui_only.load_raw.tint == 1.15
    library.widgets.load_raw.white_balance.value = 'as_shot'
    controller._wb_timer.stop()
    controller._update_white_balance()
    np.testing.assert_allclose(controller._current_preview_image, .25)


def test_duplicate_scan_cancel_confirm_and_changed_parameters(library, monkeypatch):
    controller = library.controller
    controller._current_input_image = np.ones((4, 4, 3))
    signature = controller.scan_signature()
    library.store.set_state('scan:' + signature, 'complete')
    starts, prompts = [], []
    monkeypatch.setattr(GuiController, 'run_scan', lambda self: starts.append(True))
    def no(*args):
        prompts.append(args)
        return W.QMessageBox.No
    monkeypatch.setattr(W.QMessageBox, 'question', no)
    controller.run_scan()
    assert len(prompts) == 1 and not starts
    controller.preview_divisor = 8
    assert controller.scan_signature() == signature
    monkeypatch.setattr(W.QMessageBox, 'question', lambda *args: W.QMessageBox.Yes)
    controller.run_scan()
    assert len(starts) == 1
    library.widgets.load_raw.temperature.value += 100
    controller._wb_timer.stop()
    assert controller.scan_signature() != signature
    monkeypatch.setattr(W.QMessageBox, 'question', lambda *args: (_ for _ in ()).throw(AssertionError('unexpected prompt')))
    controller.run_scan()
    assert len(starts) == 2
