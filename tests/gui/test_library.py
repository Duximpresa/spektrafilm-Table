from pathlib import Path
import json
import sqlite3
import time

import numpy as np
from PIL import Image
import pytest
from qtpy import QtCore, QtWidgets as W

from spektrafilm_gui.library import Library
from spektrafilm_gui.library_store import LibraryStore, discover_photos
from spektrafilm_gui.library_workers import thumbnail
from spektrafilm_gui.state_bridge import apply_gui_state, collect_gui_state
from spektrafilm_gui.state import clone_gui_state, PROJECT_DEFAULT_GUI_STATE
from spektrafilm_gui.table_controller import TableController
from spektrafilm_gui.widgets import create_widget_bundle
from .helpers import FakeViewer


def pump_until(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate():
        W.QApplication.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError('Background operation did not finish')
        time.sleep(.01)
    W.QApplication.processEvents()


def test_catalog_discovery_persistence_relocation_and_remove(tmp_path):
    folder = tmp_path / '照片 with spaces'
    folder.mkdir()
    a = folder / 'one.JPG'
    a.write_bytes(b'original')
    sub = folder / 'nested'
    sub.mkdir()
    b = sub / 'two.nef'
    b.write_bytes(b'raw')
    (sub / 'ignored.txt').write_text('ignore')
    assert set(discover_photos([folder])) == {str(a.resolve()), str(b.resolve())}
    db = tmp_path / 'catalog' / 'library.sqlite3'
    store = LibraryStore(db)
    first, added = store.add(a)
    assert added
    assert store.add(folder / '.' / 'one.JPG') == (first, False)
    second, _ = store.add(b)
    store.save_edits(first, {'exposure': 1.5}, 5)
    store.save_edits(second, {'exposure': -1}, 0)
    store.close()
    store = LibraryStore(db)
    assert json.loads(store.photo(first)['edits']) == {'exposure': 1.5}
    assert store.photo(first)['rotation'] == 1
    moved = folder / 'moved.JPG'
    a.rename(moved)
    store.relocate(first, moved)
    with pytest.raises(sqlite3.IntegrityError):
        store.relocate(first, b)
    store.remove(first)
    assert moved.read_bytes() == b'original'
    assert store.photo(first) is None
    assert json.loads(store.photo(second)['edits']) == {'exposure': -1}
    store.close()


def test_thumbnail_cache_and_corrupt_file(tmp_path):
    photo = tmp_path / '图像.png'
    Image.new('RGB', (600, 400), 'red').save(photo)
    cached = thumbnail(str(photo), tmp_path / 'cache')
    with Image.open(cached) as preview:
        assert preview.size == (256, 192)
        assert max(preview.getpixel((128, 0))) < 30
        assert preview.getpixel((128, 96))[0] > 200
    assert thumbnail(str(photo), tmp_path / 'cache') == cached
    Image.new('RGB', (400, 600), 'blue').save(photo)
    assert thumbnail(str(photo), tmp_path / 'cache') != cached
    bad = tmp_path / 'bad.jpg'
    bad.write_bytes(b'not an image')
    with pytest.raises(Exception):
        thumbnail(str(bad), tmp_path / 'cache')


@pytest.fixture
def library(tmp_path, monkeypatch):
    # Exercise persistence without overwriting the user's desktop preferences.
    settings_class = QtCore.QSettings

    class IsolatedSettings(settings_class):
        def __init__(self, *args, **kwargs):
            super().__init__(str(tmp_path / 'settings.ini'), settings_class.IniFormat)

    monkeypatch.setattr(QtCore, 'QSettings', IsolatedSettings)
    app = W.QApplication.instance() or W.QApplication([])
    widgets = create_widget_bundle()
    state = clone_gui_state(PROJECT_DEFAULT_GUI_STATE)
    state.simulation.workflow.auto_preview = False
    apply_gui_state(state, widgets=widgets)
    controller = TableController(viewer=FakeViewer(), widgets=widgets)
    # Exercise the real decoder and widget/state bridge without an OpenGL canvas.
    def install(image):
        controller._current_input_image = image
        controller._current_preview_image = image
    monkeypatch.setattr(controller, '_set_or_add_input_stack', install)
    window = W.QMainWindow()
    window.setCentralWidget(W.QWidget())
    view = Library(window, controller, widgets, data_dir=tmp_path / 'catalog')
    yield view
    pump_until(lambda: not view.tasks and not view.thumbnail_running)
    window.close()
    app.processEvents()


def test_import_switch_restore_and_restart(library, tmp_path):
    a, b = tmp_path / '红色 one.png', tmp_path / 'blue.png'
    Image.new('RGB', (32, 20), 'red').save(a)
    Image.new('RGB', (24, 16), 'blue').save(b)
    library.import_paths([a, b, a])
    pump_until(lambda: len(library.items) == 2 and not library.tasks)
    ids = list(library.items)
    library.open_photo(ids[0])
    pump_until(lambda: library.active_id == ids[0] and not library.controller.restoring)
    state = collect_gui_state(widgets=library.widgets)
    state.input_image.io.crop = True
    state.input_image.io.crop_center = (.3, .4)
    apply_gui_state(state, widgets=library.widgets)
    library.controller.rotation = 1
    library.open_photo(ids[1])
    pump_until(lambda: library.active_id == ids[1])
    assert not collect_gui_state(widgets=library.widgets).input_image.io.crop
    assert library.controller.rotation == 0
    library.open_photo(ids[0])
    pump_until(lambda: library.active_id == ids[0])
    restored = collect_gui_state(widgets=library.widgets)
    assert restored.input_image.io.crop
    assert tuple(restored.input_image.io.crop_center) == (.3, .4)
    assert library.controller.rotation == 1
    assert library.controller._current_input_image.shape[:2] == (32, 20)
    library.save_active()
    other = LibraryStore(tmp_path / 'catalog' / 'library.sqlite3')
    assert other.photo(ids[0])['rotation'] == 1
    assert json.loads(other.photo(ids[0])['edits'])['input_image']['crop']
    other.close()
    library.search.setText('红色')
    assert not library.items[ids[0]][0].isHidden()
    assert library.items[ids[1]][0].isHidden()


def test_load_race_and_failure_keeps_active(library, tmp_path, monkeypatch):
    a, b, bad = [tmp_path / name for name in ('a.png', 'b.png', 'bad.png')]
    for path in (a, b):
        Image.new('RGB', (24, 16), 'red').save(path)
    bad.write_bytes(b'broken')
    ids = [library.store.add(path)[0] for path in (a, b, bad)]
    library.refresh()
    library.open_photo(ids[0])
    library.open_photo(ids[1])
    pump_until(lambda: library.active_id == ids[1] and not library.tasks)
    before = library.controller._current_input_image.copy()
    messages = []
    monkeypatch.setattr(W.QMessageBox, 'warning', lambda *args: messages.append(args))
    library.open_photo(ids[2])
    pump_until(lambda: not library.controller.restoring)
    assert messages
    assert library.active_id == ids[1]
    np.testing.assert_array_equal(before, library.controller._current_input_image)
    assert library.controller._current_input_path == str(b)


def test_stale_simulation_is_never_displayed(library, monkeypatch):
    controller = library.controller
    controller._simulation_token = controller.state_token()
    controller.photo_revision += 1
    controller._active_simulation_worker = object()
    calls = []
    monkeypatch.setattr(controller, '_set_or_add_output_layer', lambda *a, **k: calls.append(a))
    controller._on_simulation_finished(object())
    assert not calls
    assert controller._active_simulation_worker is None
