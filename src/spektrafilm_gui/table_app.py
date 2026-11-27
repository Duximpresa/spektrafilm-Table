"""spektrafilm-Table entry point; upstream `spektrafilm` remains available."""
import json

from qtpy import QtCore

from spektrafilm_gui import app as upstream
from spektrafilm_gui.library import Library
from spektrafilm_gui.persistence import gui_state_from_dict, gui_state_to_dict, load_default_gui_state
from spektrafilm_gui.state_bridge import apply_gui_state
from spektrafilm_gui.table_controller import TableController


def create_app(*, data_dir=None, warmup=True):
    viewer = upstream._create_viewer()
    upstream._apply_app_palette()
    widgets = upstream._create_widgets()
    state = load_default_gui_state()
    settings = QtCore.QSettings('spektrafilm-Table', 'library')
    display = settings.value('display')
    if display:
        try:
            data = gui_state_to_dict(state)
            data['display'] = json.loads(display)
            state = gui_state_from_dict(data)
        except (ValueError, TypeError):
            pass
    apply_gui_state(state, widgets=widgets)
    controller = upstream.initialize_controller(viewer=viewer, widgets=widgets, controller_cls=TableController)
    window = upstream.build_main_window_for_app(viewer=viewer, widgets=widgets, controller=controller)
    Library(window, controller, widgets, data_dir=data_dir)
    from spektrafilm_gui.i18n import install_language
    install_language(window)
    if warmup:
        upstream._schedule_background_warmup()
    return upstream.GuiApp(viewer, widgets, controller, window)


def main():
    app = create_app()
    app.main_window.show()
    upstream.import_module('napari').run()


if __name__ == '__main__':
    main()
