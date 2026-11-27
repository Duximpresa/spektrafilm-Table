"""Run manually with native Qt to verify Develop rendering in an isolated catalog."""
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
from qtpy import QtCore, QtWidgets as W


def main():
    root = Path(tempfile.mkdtemp(prefix='spektrafilm-develop-ui-'))
    settings_type = QtCore.QSettings
    class IsolatedSettings(settings_type):
        def __init__(self, *args, **kwargs):
            super().__init__(str(root / 'settings.ini'), settings_type.IniFormat)
    QtCore.QSettings = IsolatedSettings
    from spektrafilm_gui.table_app import create_app
    from spektrafilm_gui.state_bridge import collect_gui_state, apply_gui_state
    from spektrafilm_gui.persistence import gui_state_to_dict
    app = create_app(data_dir=root / 'catalog', warmup=False)
    controller = app.controller
    library = controller.library
    state = collect_gui_state(widgets=app.widgets)
    state.simulation.workflow.auto_preview = False
    state.input_image.io.input_color_space = 'sRGB'
    state.input_image.io.input_cctf_decoding = True
    apply_gui_state(state, widgets=app.widgets)
    library.defaults = gui_state_to_dict(state)
    path = root / 'gradient.png'
    pixels = np.tile(np.linspace(35, 220, 600, dtype=np.uint8)[None, :, None], (400, 1, 3))
    Image.fromarray(pixels).save(path)
    library.import_and_open(str(path))
    app.main_window.show()
    def pump(count=1):
        for _ in range(count):
            W.QApplication.processEvents()
            time.sleep(.02)
    deadline = time.monotonic() + 30
    while library.tasks or controller.restoring:
        pump()
        assert time.monotonic() < deadline
    pump(10)
    button = app.widgets.load_raw.pick_white_balance
    button.setChecked(True)
    pump(10)
    picker = controller._layers.image_layer('white_balance_picker')
    assert picker.visible and np.max(picker.data) > .5
    image = app.viewer.screenshot(canvas_only=True)
    assert np.std(image[..., :3]) > 10
    Image.fromarray(image).save(root / 'picker.png')
    controller.refresh_preview_cache()
    pump(10)
    assert picker.visible
    assert np.std(app.viewer.screenshot(canvas_only=True)[..., :3]) > 10
    home = app.main_window.findChild(W.QPushButton, 'homeViewButton')
    assert library.preview_ratio.parentWidget() is home.parentWidget()
    assert abs(library.preview_ratio.geometry().center().y() - home.geometry().center().y()) <= 2
    assert library.modules.tabText(1) == '显影'
    app.main_window.grab().save(str(root / 'chinese.png'))
    controller.run_preview = lambda: None
    controller._pick_white_balance(app.viewer, SimpleNamespace(position=picker.data_to_world((200, 300))))
    assert not button.isChecked()
    assert app.widgets.load_raw.white_balance.value == 'custom'
    pump(10)
    library.change_language('en')
    pump(10)
    assert library.modules.tabText(1) == 'Develop'
    app.main_window.grab().save(str(root / 'english.png'))
    print('Native rendering, picker refresh/sample, footer position and languages verified:', root, flush=True)
    app.main_window.close()
    app.viewer.close()


if __name__ == '__main__':
    main()
