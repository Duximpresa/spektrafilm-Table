from types import SimpleNamespace
import json
import numpy as np
from qtpy import QtCore, QtWidgets as W
from spektrafilm_gui.live_white_balance import apply_white_balance, fit_white_balance
from spektrafilm_gui.persistence import gui_state_from_dict, gui_state_to_dict
from spektrafilm_gui.state import PROJECT_DEFAULT_GUI_STATE
from spektrafilm_gui.cache_settings import clean_cache, cache_size
from .test_library import library, pump_until
from .test_table_workspace import make_photo


def test_fit_recovers_camera_balance_and_neutral_picker():
    source = np.random.default_rng(4).uniform(.08, .3, (12, 15, 3))
    raw = SimpleNamespace(white_balance='custom', temperature=4600, tint=1.18)
    target = apply_white_balance(source, raw, 'sRGB', False)
    temperature, tint = fit_white_balance(source, target, 'sRGB', False)
    assert abs(temperature - 4600) < 5
    assert abs(tint - 1.18) < .002
    patch = np.full((5, 5, 3), [.2, .25, .3])
    temperature, tint = fit_white_balance(patch, np.full_like(patch, .3), 'sRGB', False)
    adjusted = apply_white_balance(patch, SimpleNamespace(white_balance='custom', temperature=temperature, tint=tint), 'sRGB', False)
    assert np.ptp(adjusted[0, 0]) < .001


def test_cache_only_removes_owned_thumbnails(tmp_path):
    original = tmp_path / 'photo.jpg'
    original.write_bytes(b'original')
    database = tmp_path / 'library.sqlite3'
    database.write_bytes(b'edits')
    cached = tmp_path / ('a' * 64 + '.jpg')
    cached.write_bytes(b'cache')
    assert cache_size(tmp_path) == 5
    clean_cache(tmp_path)
    assert not cached.exists()
    assert original.read_bytes() == b'original'
    assert database.read_bytes() == b'edits'


def test_config_v2_and_legacy():
    data = gui_state_to_dict(PROJECT_DEFAULT_GUI_STATE)
    assert data['schema_version'] == 2
    assert 'temperature' not in data['load_raw']
    legacy = dict(data)
    legacy.pop('schema_version')
    legacy['load_raw'] = {**legacy['load_raw'], **legacy.pop('white_balance')}
    assert gui_state_from_dict(legacy) == gui_state_from_dict(data)


def test_multiselect_paste_persists_all_targets(library, tmp_path):
    paths = [make_photo(tmp_path / f'{i}.jpg') for i in range(3)]
    library.import_paths(paths)
    pump_until(lambda: len(library.items) == 3 and not library.tasks)
    ids = list(library.items)
    library.open_photo(ids[0])
    pump_until(lambda: library.active_id == ids[0] and not library.controller.restoring)
    library.widgets.load_raw.temperature.value = 4300
    library.controller._wb_timer.stop()
    library.copy_parameters(ids[0])
    library.strip.clearSelection()
    for photo_id in ids[1:]:
        library.items[photo_id][1].setSelected(True)
    library.strip.setCurrentItem(library.items[ids[1]][1], QtCore.QItemSelectionModel.NoUpdate)
    pump_until(lambda: not library.controller.restoring)
    assert len(library.strip.selectedItems()) == 2
    library.paste_parameters()
    pump_until(lambda: not library.controller.restoring)
    assert len(library.strip.selectedItems()) == 2
    for photo_id in ids[1:]:
        restored = gui_state_from_dict(json.loads(library.store.photo(photo_id)['edits']))
        assert restored.gui_only.load_raw.temperature == 4300
    assert library.strip.selectionMode() == W.QAbstractItemView.ExtendedSelection
    library.show_library()
    assert library.histogram.isHidden()
    library.open_photo(ids[2])
    pump_until(lambda: not library.controller.restoring)
    assert not library.histogram.isHidden()


def test_native_ctrl_shift_selection(library, tmp_path):
    from qtpy.QtTest import QTest
    paths = [make_photo(tmp_path / f'select-{i}.jpg') for i in range(4)]
    library.import_paths(paths)
    pump_until(lambda: len(library.items) == 4 and not library.tasks)
    library.window.resize(1200, 800)
    library.window.show()
    W.QApplication.processEvents()
    view = library.strip
    def click(index, modifier=QtCore.Qt.NoModifier):
        QTest.mouseClick(view.viewport(), QtCore.Qt.LeftButton, modifier,
                         view.visualItemRect(view.item(index)).center())
        W.QApplication.processEvents()
    click(0)
    click(2, QtCore.Qt.ControlModifier)
    assert {view.row(i) for i in view.selectedItems()} == {0, 2}
    click(1)
    click(3, QtCore.Qt.ShiftModifier)
    assert {view.row(i) for i in view.selectedItems()} == {1, 2, 3}


def test_picker_survives_preview_refresh_and_restores_visibility(library, monkeypatch):
    from spektrafilm_gui.controller import GuiController, INPUT_PREVIEW_LAYER_NAME
    from .helpers import FakeLayer
    controller = library.controller
    pixels = np.full((20, 30, 3), .45, dtype=np.float32)
    controller._current_input_image = pixels
    preview = FakeLayer(pixels, name=INPUT_PREVIEW_LAYER_NAME, visible=False)
    output = FakeLayer(pixels, name='output', visible=True)
    controller._viewer.layers.extend([preview, output])
    controller._viewer.layers.selection.active = output
    button = library.widgets.load_raw.pick_white_balance
    button.setChecked(True)
    picker = controller._layers.image_layer('white_balance_picker')
    assert picker.visible and not output.visible
    assert picker.contrast_limits == (0., 1.)
    np.testing.assert_array_equal(picker.data, pixels)
    def refresh(_self):
        preview.visible = False
        output.visible = True
    monkeypatch.setattr(GuiController, 'refresh_preview_cache', refresh)
    controller.refresh_preview_cache()
    assert picker.visible and not output.visible
    button.setChecked(False)
    assert controller._layers.image_layer('white_balance_picker') is None
    assert output.visible and not preview.visible
    assert controller._viewer.layers.selection.active is output


def test_language_switch_preserves_parameters_and_translates_new_dialog(library):
    from spektrafilm_gui.i18n import install_language
    from spektrafilm_gui.cache_settings import CacheSettings
    from spektrafilm_gui.state_bridge import collect_gui_state
    before = gui_state_to_dict(collect_gui_state(widgets=library.widgets))
    manager = install_language(library.window, 'en')
    try:
        library.change_language('zh_CN')
        assert library.modules.tabText(1) == '显影'
        assert library.settings_menu.title() == '设置'
        assert library.widgets.load_raw.white_balance.currentText() == '拍摄时设置'
        assert library.widgets.load_raw.white_balance.value == 'as_shot'
        assert gui_state_to_dict(collect_gui_state(widgets=library.widgets)) == before
        dialog = CacheSettings(library)
        dialog.show()
        W.QApplication.processEvents()
        assert dialog.windowTitle() == '设置 · 缓存'
        dialog.close()
        assert QtCore.QSettings('spektrafilm-Table', 'library').value('language') == 'zh_CN'
        library.change_language('en')
        assert library.modules.tabText(1) == 'Develop'
        assert library.widgets.load_raw.white_balance.currentText() == 'as_shot'
        assert gui_state_to_dict(collect_gui_state(widgets=library.widgets)) == before
    finally:
        manager.dispose()
        manager.deleteLater()
