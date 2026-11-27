import json
from pathlib import Path
import sqlite3

from PIL import Image
from qtpy import QtCore, QtWidgets as W

from spektrafilm_gui.import_preview import ImportPreview
from spektrafilm_gui.library import Library
from spektrafilm_gui.library_store import LibraryStore, canonical_path, discover_photos
from spektrafilm_gui.preset_paths import PresetPaths
from spektrafilm_gui.table_controller import TableController
from .helpers import FakeViewer
from .test_library import library, pump_until


def make_photo(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (24, 16), 'orange').save(path)
    return path


def test_v1_migration_preserves_edits_and_missing_folders(tmp_path):
    path = tmp_path / 'v1.sqlite3'
    original = tmp_path / 'missing' / 'image.jpg'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE photos(id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL, path_key TEXT NOT NULL UNIQUE, edits TEXT, rotation INTEGER NOT NULL DEFAULT 0)')
        db.execute('INSERT INTO photos VALUES (42,?,?,?,3)',
                   (str(original), canonical_path(original), '{"camera":{"exposure_compensation_ev":1.5}}'))
        db.execute('PRAGMA user_version=1')
    store = LibraryStore(path)
    assert store.photo(42)['rotation'] == 3
    assert json.loads(store.photo(42)['edits'])['camera']['exposure_compensation_ev'] == 1.5
    assert store.folders()[0]['path_key'] == canonical_path(original.parent)
    assert store.connection.execute('PRAGMA user_version').fetchone()[0] == 2
    store.close()


def test_folder_filter_and_last_photo_restore(library, tmp_path):
    root = tmp_path / '旅行'
    first = make_photo(root / 'one' / 'same' / 'a.jpg')
    second = make_photo(root / 'one' / 'same' / 'b.jpg')
    third = make_photo(root / 'two' / 'same' / 'c.jpg')
    library.store.register_folder(root)
    ids = [library.store.add(path)[0] for path in (first, second, third)]
    library.refresh()
    assert canonical_path(root / 'one') in library.folder_items
    library.folders.setCurrentItem(library.folder_items[canonical_path(first.parent)])
    assert library.active_id is None  # Browsing folders does not decode or simulate.
    assert library.visible_ids() == ids[:2]
    assert library.items[ids[2]][1].isHidden()
    library.modules.setCurrentIndex(1)
    pump_until(lambda: library.active_id == ids[0])
    library.open_photo(ids[1])
    pump_until(lambda: library.active_id == ids[1])
    library.folders.setCurrentItem(library.folder_items[canonical_path(third.parent)])
    pump_until(lambda: library.active_id == ids[2])
    library.folders.setCurrentItem(library.folder_items[canonical_path(first.parent)])
    pump_until(lambda: library.active_id == ids[1])
    library.modules.setCurrentIndex(0)
    assert library.stack.currentIndex() == 0
    assert library.active_id == ids[1]


def test_empty_develop_and_restart_module(library, tmp_path):
    library.thumbnail_slider.setValue(190)
    library.modules.setCurrentIndex(1)
    assert library.stack.currentIndex() == 1
    assert library.editor_stack.currentIndex() == 0
    assert not library.editor.isEnabled()
    library.window.close()
    controller = TableController(viewer=FakeViewer(), widgets=library.widgets)
    window = W.QMainWindow()
    window.setCentralWidget(W.QWidget())
    restored = Library(window, controller, library.widgets, data_dir=tmp_path / 'catalog')
    assert restored.modules.currentIndex() == restored.stack.currentIndex() == 1
    assert restored.thumbnail_slider.value() == 190
    assert restored.strip.iconSize().width() == 190
    window.close()


def test_filmstrip_spans_both_columns_and_resizes(library):
    library.window.resize(1200, 850)
    library.window.show()
    W.QApplication.processEvents()
    assert library.workspace_split.widget(1) is library.filmstrip_panel
    assert library.filmstrip_panel.width() > library.folders.width() + library.stack.width() - 20
    library.workspace_split.setSizes([500, 260])
    library.save_strip_height()
    height = int(library.store.get_state('filmstrip_height'))
    assert height > 130
    library.thumbnail_slider.setValue(240)
    assert library.strip.iconSize().width() == 240
    assert library.strip.maximumHeight() > 10000


def test_scan_progress_updates_and_rejects_old_tasks(library):
    controller = library.controller
    controller._simulation_token = controller.state_token()
    controller._active_simulation_label = 'Scan'
    library.scan_progress(controller.scan_run_id, 'filming.expose', 1, 7)
    assert library.scan_bar.value() == 1
    assert 'Film exposure' in library.scan_label.text()
    library.scan_progress(controller.scan_run_id - 1, 'printing.develop', 5, 7)
    assert library.scan_bar.value() == 1
    library.finish_scan('SCAN complete', success=True)
    assert library.scan_started is None
    assert library.scan_bar.format() == 'Complete'
    controller._active_simulation_label = None
    library.scan_progress(controller.scan_run_id, 'printing.develop', 5, 7)
    assert library.scan_started is None


def test_module_switch_cancels_late_load(library, tmp_path):
    photo = make_photo(tmp_path / 'pending.jpg')
    photo_id, _ = library.store.add(photo)
    library.refresh()
    library.open_photo(photo_id)
    library.modules.setCurrentIndex(0)
    pump_until(lambda: not library.tasks and not library.pending_thumbnails)
    assert library.stack.currentIndex() == 0
    assert library.active_id is None


def test_import_preview_selection_duplicate_and_cancel(library, tmp_path):
    a, b = [make_photo(tmp_path / name) for name in ('a.jpg', 'b.jpg')]
    library.store.add(a)
    preview = ImportPreview(library, existing_paths=[canonical_path(a)], cache=library.cache, paths=[str(a), str(b)])
    pump_until(lambda: not preview.scanning)
    assert preview.checked_paths() == [str(b.resolve())]
    assert not preview.rows[str(a.resolve())].flags() & QtCore.Qt.ItemIsEnabled
    preview.check_all(False)
    assert not preview.import_button.isEnabled()
    preview.check_all(True)
    assert preview.import_button.isEnabled()
    preview.reject()
    pump_until(lambda: not preview.tasks)
    assert len(library.store.photos()) == 1


def test_import_preview_stale_scan_and_recursive_toggle(library, tmp_path):
    a = make_photo(tmp_path / 'first' / 'a.jpg')
    b = make_photo(tmp_path / 'second' / 'sub' / 'b.jpg')
    preview = ImportPreview(library, existing_paths=[], cache=library.cache)
    preview.sources = [str(a.parent)]
    preview.scan()
    preview.sources = [str(b.parent.parent)]
    preview.scan()
    pump_until(lambda: not preview.scanning)
    assert preview.checked_paths() == [str(b.resolve())]
    preview.recursive.setChecked(False)
    pump_until(lambda: not preview.scanning)
    assert not preview.rows
    assert not preview.import_button.isEnabled()
    assert list(discover_photos([b.parent.parent], recursive=False)) == []
    preview.reject()
    pump_until(lambda: not preview.tasks)


def test_import_preview_corrupt_still_selectable(library, tmp_path):
    bad = tmp_path / 'corrupt.jpg'
    bad.write_bytes(b'corrupt')
    preview = ImportPreview(library, existing_paths=[], cache=library.cache, paths=[str(bad)])
    pump_until(lambda: not preview.tasks and not preview.scanning and not preview.queue)
    assert 'Preview unavailable' in preview.rows[str(bad)].text()
    assert preview.checked_paths() == [str(bad)]
    preview.accept()
    assert preview.selected_paths == [str(bad)]
    assert not library.store.photos()


def test_import_preview_read_error(library, monkeypatch):
    from spektrafilm_gui import import_preview
    def denied(*args, **kwargs):
        raise PermissionError('Access denied to source folder')
    monkeypatch.setattr(import_preview, 'discover_photos', denied)
    preview = ImportPreview(library, existing_paths=[], cache=library.cache, paths=['unreadable'])
    pump_until(lambda: not preview.scanning)
    assert 'Could not read folder' in preview.status.text()
    assert 'Access denied' in preview.status.text()
    assert not preview.import_button.isEnabled()
    preview.reject()
    pump_until(lambda: not preview.tasks)


def test_missing_folder_and_relocation(library, tmp_path):
    path = make_photo(tmp_path / 'old' / 'a.jpg')
    photo_id, _ = library.store.add(path)
    moved = tmp_path / 'new' / 'a.jpg'
    moved.parent.mkdir()
    path.rename(moved)
    path.parent.rmdir()
    library.refresh()
    old_key = canonical_path(path.parent)
    assert 'Missing' in library.folder_items[old_key].text(0)
    library.folders.setCurrentItem(library.folder_items[old_key])
    library.modules.setCurrentIndex(1)
    assert library.editor_stack.currentIndex() == 0
    assert not library.editor.isEnabled()
    library.store.relocate(photo_id, moved)
    library.refresh()
    assert library.store.photos_in_folder(old_key) == []
    assert library.store.photos_in_folder(moved.parent)[0]['id'] == photo_id


def test_import_preview_raw_embedded_thumbnail(library, tmp_path, monkeypatch):
    from io import BytesIO
    from types import SimpleNamespace
    import rawpy
    raw_path = tmp_path / 'raw photo.nef'
    raw_path.write_bytes(b'test fixture')
    encoded = BytesIO()
    Image.new('RGB', (40, 30), 'blue').save(encoded, 'JPEG')
    class Raw:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def extract_thumb(self):
            return SimpleNamespace(format=rawpy.ThumbFormat.JPEG, data=encoded.getvalue())
    monkeypatch.setattr(rawpy, 'imread', lambda path: Raw())
    preview = ImportPreview(library, existing_paths=[], cache=library.cache, paths=[str(raw_path)])
    pump_until(lambda: not preview.tasks and not preview.scanning and not preview.queue)
    assert 'unavailable' not in preview.rows[str(raw_path)].text()
    assert list(library.cache.glob('*.jpg'))
    preview.reject()


class MemorySettings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=''):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


def test_presets_default_remember_missing_and_install_fallback(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    (root / 'src' / 'spektrafilm_gui').mkdir(parents=True)
    (root / 'pyproject.toml').touch()
    paths = PresetPaths(settings=MemorySettings(), project_root=root, user_root=tmp_path / 'user')
    assert paths.initial_directory() == root / 'presets'
    custom = tmp_path / 'personal'
    custom.mkdir()
    paths.remember(custom / 'preset.json')
    assert paths.initial_directory() == custom
    custom.rmdir()
    assert paths.initial_directory() == root / 'presets'
    paths.project_root = tmp_path / 'installed'
    assert paths.initial_directory() == tmp_path / 'user' / 'presets'
    paths.project_root = root
    import spektrafilm_gui.preset_paths as module
    original = module.writable_directory
    monkeypatch.setattr(module, 'writable_directory', lambda p: False if p == root / 'presets' else original(p))
    assert paths.initial_directory() == tmp_path / 'user' / 'presets'


def test_preset_dialog_remembers_only_success(library, tmp_path, monkeypatch):
    from spektrafilm_gui import preset_paths
    paths = PresetPaths(settings=MemorySettings(), project_root=tmp_path / 'absent', user_root=tmp_path / 'user')
    monkeypatch.setattr(preset_paths, 'PresetPaths', lambda: paths)
    monkeypatch.setattr(W.QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    library.controller.save_current_state_to_file()
    assert paths.settings.values == {}
    destination = tmp_path / 'custom'
    destination.mkdir()
    filename = destination / 'my.json'
    monkeypatch.setattr(W.QFileDialog, 'getSaveFileName', lambda *args: (str(filename), ''))
    library.controller.save_current_state_to_file()
    assert filename.exists()
    assert paths.initial_directory() == destination
    previous = dict(paths.settings.values)
    invalid = tmp_path / 'bad.json'
    invalid.write_text('{broken')
    monkeypatch.setattr(W.QMessageBox, 'warning', lambda *args: None)
    monkeypatch.setattr(W.QFileDialog, 'getOpenFileName', lambda *args: (str(invalid), ''))
    library.controller.load_state_from_file()
    assert paths.settings.values == previous
    good = tmp_path / 'good.json'
    good.write_bytes(filename.read_bytes())
    monkeypatch.setattr(W.QFileDialog, 'getOpenFileName', lambda *args: (str(good), ''))
    library.controller.load_state_from_file()
    assert paths.initial_directory() == tmp_path


def test_compute_selection_persists_outside_photo_edits(library, tmp_path):
    controller = library.controller
    before = controller.state_token()
    defaults = dict(library.defaults)
    library.execution_combo.setCurrentIndex(library.execution_combo.findData('cuda'))
    assert controller.execution_backend == 'cuda'
    assert controller.state_token() != before
    assert library.store.get_state('execution_backend') == 'cuda'
    assert library.defaults == defaults
    controller._set_simulation_controls_enabled(False)
    assert not library.execution_combo.isEnabled()
    controller._set_simulation_controls_enabled(True)
    assert library.execution_combo.isEnabled()
    controller._simulation_token = controller.state_token()
    library.update_execution_status(controller.scan_run_id, 'CUDA float64 + CPU')
    assert library.execution_status.toolTip() == 'CUDA float64 + CPU'
    library.update_execution_status(controller.scan_run_id - 1, 'old result')
    assert library.execution_status.toolTip() == 'CUDA float64 + CPU'
    library.window.close()
    restored_controller = TableController(viewer=FakeViewer(), widgets=library.widgets)
    window = W.QMainWindow()
    window.setCentralWidget(W.QWidget())
    restored = Library(window, restored_controller, library.widgets, data_dir=tmp_path / 'catalog')
    assert restored.execution_combo.currentData() == 'cuda'
    assert restored_controller.execution_backend == 'cuda'
    window.close()


def test_switch_backend_recreates_runtime_on_worker(library, monkeypatch):
    from types import SimpleNamespace
    import numpy as np
    import spektrafilm_gui.controller as module
    controller = library.controller
    calls = []
    class FakeSimulator:
        def __init__(self, params, *, execution=None):
            calls.append(('create', execution.backend if execution else 'cpu'))
        def process(self, image, **kwargs):
            return image
        def update_params(self, params):
            calls.append(('update',))
        def close(self):
            calls.append(('close',))
    monkeypatch.setattr(module, 'runtime_simulator', FakeSimulator)
    monkeypatch.setattr(module, 'digest_params', lambda params, **kwargs: params)
    image = np.zeros((2, 2, 3))
    controller._process_image_with_runtime(image, SimpleNamespace())
    controller._requested_backend = 'cuda'
    controller._process_image_with_runtime(image, SimpleNamespace())
    controller._process_image_with_runtime(image, SimpleNamespace())
    controller._requested_backend = 'cpu'
    controller._process_image_with_runtime(image, SimpleNamespace())
    assert calls == [('create', 'cpu'), ('close',), ('create', 'cuda'), ('update',), ('close',), ('create', 'cpu')]


def test_real_cuda_scan_and_cpu_switch_in_qt_worker(library, monkeypatch):
    import os
    import numpy as np
    import pytest
    if os.environ.get('SPEKTRAFILM_TEST_CUDA') != '1':
        pytest.skip('requires real CUDA')
    controller = library.controller
    controller._current_input_image = np.full((24, 32, 3), .18)
    controller._current_preview_image = controller._current_input_image
    outputs, errors = [], []
    monkeypatch.setattr(controller, '_set_or_add_output_layer', lambda image, **kwargs: outputs.append(kwargs['float_image']))
    def failed(message):
        errors.append(message)
        controller._active_simulation_worker = None
        controller._active_simulation_label = None
    monkeypatch.setattr(controller, '_on_simulation_failed', failed)
    for backend in ('cuda', 'cpu', 'cuda'):
        library.execution_combo.setCurrentIndex(library.execution_combo.findData(backend))
        controller.run_scan()
        assert not library.execution_combo.isEnabled()
        pump_until(lambda: errors or controller._active_simulation_worker is None, timeout=90)
        assert not errors
        assert library.execution_combo.isEnabled()
        assert controller._runtime_backend == backend
        assert np.isfinite(outputs[-1]).all()
        if backend == 'cuda':
            assert controller._runtime_simulator._pipeline.backend.gpu_calls > 0
            assert 'CUDA float64' in library.execution_status.toolTip()
        else:
            assert library.execution_status.toolTip() == 'CPU'
    assert len(outputs) == 3
