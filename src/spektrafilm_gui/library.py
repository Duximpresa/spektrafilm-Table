"""Photo library and filmstrip for the original spektrafilm editor."""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from time import monotonic
import sqlite3

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets as W

from spektrafilm_gui.library_store import IMAGE_EXTENSIONS, RAW_EXTENSIONS, LibraryStore, discover_photos
from spektrafilm_gui.library_workers import Task, decode_live_photo as decode_photo, thumbnail
from spektrafilm_gui.import_preview import ImportPreview
from spektrafilm_gui.persistence import gui_state_from_dict, gui_state_to_dict
from spektrafilm_gui.state_bridge import apply_gui_state, collect_gui_state


class Library(W.QWidget):
    def __init__(self, window, controller, widgets, *, data_dir=None):
        super().__init__()
        self.window, self.controller, self.widgets = window, controller, widgets
        controller.library = self
        root = Path(data_dir) if data_dir else Path(QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.GenericDataLocation)) / 'spektrafilm-Table'
        self.store = LibraryStore(root / 'library.sqlite3')
        self.cache = Path(self.store.get_state('cache_directory', str(root / 'thumbnails')))
        self.copied_edits = None
        self.defaults = gui_state_to_dict(collect_gui_state(widgets=widgets))
        self.active_id = None
        self.load_serial = 0
        self.saved = None
        self.tasks = {}
        self.pending_thumbnails = deque()
        self.thumbnail_running = False
        self.closed = False
        self.closing = False
        self.pool = QtCore.QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.items = {}
        self.dialogs = []
        self.current_folder = self.store.get_state('folder')
        self.folder_items = {}
        self.import_target = None
        self.stack = W.QStackedWidget()
        self.grid = self._list(192, 144)
        self.strip = self._list(112, 84)
        self.strip.setWrapping(False)
        self.strip.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.strip.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.strip.customContextMenuRequested.connect(self.strip_menu)
        self.strip.setMinimumHeight(55)
        self.strip.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.search = W.QLineEdit()
        self.search.setPlaceholderText('Search filenames')
        self.search.textChanged.connect(self.filter)
        self.count = W.QLabel()
        self.progress = W.QLabel('Import photos to start. Originals stay in their current folders.')
        self.import_button = W.QPushButton('Import photos')
        self.folder_button = W.QPushButton('Import folder')
        self.import_button.clicked.connect(self.choose_files)
        self.folder_button.clicked.connect(self.choose_folder)
        remove = W.QPushButton('Remove from library')
        remove.clicked.connect(self.remove_selected)
        relocate = W.QPushButton('Locate original')
        relocate.clicked.connect(self.relocate_selected)
        toolbar = W.QHBoxLayout()
        for widget in (self.import_button, self.folder_button, self.search, remove, relocate, self.count):
            toolbar.addWidget(widget)
        page = W.QWidget()
        layout = W.QVBoxLayout(page)
        layout.addLayout(toolbar)
        layout.addWidget(self.grid, 1)
        layout.addWidget(self.progress)
        self.stack.addWidget(page)
        self.editor = window.takeCentralWidget()
        edit_page = W.QWidget()
        edit_layout = W.QVBoxLayout(edit_page)
        self.editor_stack = W.QStackedWidget()
        self.empty_editor = W.QLabel('Select a photo from a folder or import photos to begin editing.')
        self.empty_editor.setAlignment(QtCore.Qt.AlignCenter)
        self.empty_editor.setWordWrap(True)
        self.editor_stack.addWidget(self.empty_editor)
        self.editor_stack.addWidget(self.editor)
        self.editor.setEnabled(False)
        edit_layout.addWidget(self.editor_stack, 1)
        self.stack.addWidget(edit_page)
        self.modules = W.QTabBar()
        self.modules.addTab('Library')
        self.modules.addTab('Develop')
        self.modules.setExpanding(False)
        self.modules.setStyleSheet('QTabBar::tab { padding: 12px 24px; font-size: 16px; }')
        self.modules.currentChanged.connect(self.switch_module)
        self.folders = W.QTreeWidget()
        self.folders.setHeaderLabel('Folders')
        self.folders.setMinimumWidth(180)
        self.folders.currentItemChanged.connect(self.folder_changed)
        split = W.QSplitter()
        from spektrafilm_gui.histogram import Histogram
        self.histogram = Histogram()
        self.histogram.hide()
        sidebar = W.QWidget()
        sidebar_layout = W.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self.histogram)
        sidebar_layout.addWidget(self.folders, 1)
        split.addWidget(sidebar)
        split.addWidget(self.stack)
        split.setStretchFactor(1, 1)
        split.setSizes([230, 1100])
        outer = W.QVBoxLayout(self)
        top = W.QHBoxLayout()
        title = W.QLabel('spektrafilm-Table')
        title.setStyleSheet('font-size: 20px; padding: 8px;')
        top.addWidget(title)
        top.addStretch()
        from spektrafilm.runtime.execution import BACKENDS
        self.execution_combo = W.QComboBox()
        self.execution_combo.setObjectName('execution_backend')
        for backend in BACKENDS:
            self.execution_combo.addItem(backend.label, backend.id)
        saved_backend = self.store.get_state('execution_backend', 'cpu')
        index = self.execution_combo.findData(saved_backend)
        self.execution_combo.setCurrentIndex(max(0, index))
        controller.execution_backend = self.execution_combo.currentData()
        controller._requested_backend = controller.execution_backend
        self.execution_combo.setToolTip(
            'CUDA accelerates diffusion and CAM16-UCS in double precision. '
            'Other steps use CPU. Missing CUDA or GPU memory falls back to CPU.')
        self.execution_combo.currentIndexChanged.connect(self.change_execution_backend)
        self.execution_status = W.QLabel('CPU' if controller.execution_backend == 'cpu' else 'CUDA · checked on first calculation')
        self.execution_status.setMaximumWidth(340)
        self.preview_ratio = W.QComboBox()
        self.preview_ratio.addItem('Auto', 0)
        for divisor in (1, 2, 4, 8, 16):
            self.preview_ratio.addItem('1/' + str(divisor), divisor)
        ratio = int(self.store.get_state('preview_ratio', '0'))
        self.preview_ratio.setCurrentIndex(max(0, self.preview_ratio.findData(ratio)))
        controller.preview_divisor = self.preview_ratio.currentData()
        def change_ratio():
            controller.preview_divisor = self.preview_ratio.currentData()
            self.store.set_state('preview_ratio', str(controller.preview_divisor))
            controller.refresh_preview_cache()
            controller.request_auto_preview()
        self.preview_ratio.currentIndexChanged.connect(change_ratio)
        self.preview_ratio.setToolTip('Preview dimensions relative to the original. SCAN always uses full resolution.')
        self.preview_size_label = W.QLabel('Preview size')
        home_button = self.editor.findChild(W.QPushButton, 'homeViewButton')
        if home_button is not None:
            footer = home_button.parentWidget()
            footer.layout().addWidget(self.preview_size_label)
            footer.layout().addWidget(self.preview_ratio)
            self.preview_ratio.setFixedHeight(home_button.height())
            self.preview_ratio.setMaximumWidth(90)
        top.addWidget(W.QLabel('Compute'))
        top.addWidget(self.execution_combo)
        top.addWidget(self.execution_status)
        controller.scan_signals.execution.connect(self.update_execution_status)
        self.settings_menu = window.menuBar().addMenu('Settings')
        self.settings_menu.addAction('Cache…', self.show_cache_settings)
        self.language_menu = self.settings_menu.addMenu('Language')
        self.language_actions = {}
        action_group = QtGui.QActionGroup(self)
        for code, label in (('zh_CN', '简体中文'), ('en', 'English')):
            action = self.language_menu.addAction(label)
            action.setCheckable(True)
            action_group.addAction(action)
            action.triggered.connect(lambda checked, code=code: self.change_language(code))
            self.language_actions[code] = action
        saved_language = QtCore.QSettings('spektrafilm-Table', 'library').value('language', 'zh_CN')
        self.language_actions.get(saved_language, self.language_actions['zh_CN']).setChecked(True)
        top.addWidget(self.modules)
        outer.addLayout(top)
        self.filmstrip_panel = W.QWidget()
        strip_layout = W.QVBoxLayout(self.filmstrip_panel)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_header = W.QHBoxLayout()
        strip_header.addWidget(W.QLabel('Photos'))
        strip_header.addSpacing(12)
        self.scan_label = W.QLabel()
        self.scan_bar = W.QProgressBar()
        self.scan_bar.setFixedWidth(190)
        self.scan_bar.setVisible(False)
        self.scan_bar.setToolTip('Progress measures completed processing steps, not remaining time.')
        strip_header.addWidget(self.scan_label)
        strip_header.addWidget(self.scan_bar)
        strip_header.addStretch()
        strip_header.addWidget(W.QLabel('Thumbnail size'))
        self.thumbnail_slider = W.QSlider(QtCore.Qt.Horizontal)
        self.thumbnail_slider.setRange(80, 256)
        self.thumbnail_slider.setFixedWidth(190)
        self.thumbnail_slider.setValue(int(self.store.get_state('thumbnail_size', '112')))
        self.thumbnail_slider.valueChanged.connect(self.resize_thumbnails)
        strip_header.addWidget(self.thumbnail_slider)
        strip_layout.addLayout(strip_header)
        strip_layout.addWidget(self.strip, 1)
        self.workspace_split = W.QSplitter(QtCore.Qt.Vertical)
        self.workspace_split.setChildrenCollapsible(False)
        self.workspace_split.setHandleWidth(8)
        self.workspace_split.setStyleSheet('QSplitter::handle:vertical { background: #303030; } '
                                          'QSplitter::handle:vertical:hover { background: #f5a16e; }')
        self.workspace_split.addWidget(split)
        self.workspace_split.addWidget(self.filmstrip_panel)
        self.workspace_split.handle(1).setToolTip('Drag to resize the filmstrip')
        self.workspace_split.setStretchFactor(0, 1)
        self.workspace_split.setStretchFactor(1, 0)
        height = max(100, min(700, int(self.store.get_state('filmstrip_height', '180'))))
        self.workspace_split.setSizes([700, height])
        self.workspace_split.splitterMoved.connect(self.save_strip_height)
        outer.addWidget(self.workspace_split, 1)
        self.scan_started = None
        self.scan_stage = ''
        self.scan_timer = QtCore.QTimer(self)
        self.scan_timer.setInterval(500)
        self.scan_timer.timeout.connect(self.update_scan_elapsed)
        controller.scan_signals.progress.connect(self.scan_progress)
        self.resize_thumbnails(self.thumbnail_slider.value())
        window.setCentralWidget(self)
        window.setWindowTitle('spektrafilm-Table')
        self.grid.itemDoubleClicked.connect(lambda item: self.open_photo(item.data(QtCore.Qt.UserRole)))
        self.grid.currentItemChanged.connect(self.select_grid)
        self.strip.currentItemChanged.connect(self.select_strip)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(600)
        self.timer.timeout.connect(self.autosave)
        self.timer.start()
        self.cache_timer = QtCore.QTimer(self)
        self.cache_timer.setInterval(60000)
        self.cache_timer.timeout.connect(self.trim_cache)
        self.cache_timer.start()
        self.trim_cache()
        window.installEventFilter(self)
        settings = QtCore.QSettings('spektrafilm-Table', 'library')
        geometry = settings.value('geometry')
        if geometry is not None:
            window.restoreGeometry(geometry)
        self.refresh()
        selected = self.store.get_state('selected_photo')
        selected_id = int(selected) if selected.isdigit() else self.folder_photo()
        self.set_selected(selected_id if selected_id in self.visible_ids() else self.folder_photo())
        self.modules.setCurrentIndex(int(self.store.get_state('module', '0')) if self.store.get_state('module', '0') in ('0', '1') else 0)

    def change_language(self, language):
        from spektrafilm_gui.i18n import install_language
        manager = getattr(W.QApplication.instance(), '_table_localizer', None)
        if manager is None:
            manager = install_language(self.window, language)
        manager.set_language(language)
        self.language_actions[language].setChecked(True)
        self.histogram.update()

    def update_histogram(self):
        self.histogram.set_image(self.controller._current_preview_image)

    def show_cache_settings(self):
        from spektrafilm_gui.cache_settings import CacheSettings
        CacheSettings(self).exec()

    def trim_cache(self):
        if self.closed or self.closing or self.tasks or any(d.tasks for d in self.dialogs):
            return
        if self.store.get_state('cache_auto', '1') == '1':
            from spektrafilm_gui.cache_settings import clean_cache
            try:
                clean_cache(self.cache, int(self.store.get_state('cache_limit_mb', '1024')) * 1024**2)
            except OSError as exc:
                self.window.statusBar().showMessage('Cache cleanup failed: ' + str(exc))

    def strip_menu(self, position):
        item = self.strip.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.strip.setCurrentItem(item)
        menu = W.QMenu(self.strip)
        copy_action = menu.addAction('Copy parameters')
        paste_action = menu.addAction('Paste parameters to selected photos')
        paste_action.setEnabled(self.copied_edits is not None and not self.controller.restoring)
        action = menu.exec(self.strip.mapToGlobal(position))
        if action == copy_action:
            self.copy_parameters(item.data(QtCore.Qt.UserRole))
        elif action == paste_action:
            self.paste_parameters()

    def copy_parameters(self, photo_id):
        if not self.save_active() or self.controller.restoring:
            return
        row = self.store.photo(photo_id)
        if row:
            self.copied_edits = json.loads(row['edits']) if row['edits'] else json.loads(json.dumps(self.defaults))
            self.copied_edits.pop('display', None)

    def paste_parameters(self):
        if self.copied_edits is None or self.controller.restoring or not self.save_active():
            return
        ids = [item.data(QtCore.Qt.UserRole) for item in self.strip.selectedItems() if not item.isHidden()]
        try:
            with self.store.connection:
                for photo_id in ids:
                    self.store.connection.execute('UPDATE photos SET edits=? WHERE id=?',
                        (json.dumps(self.copied_edits), photo_id))
            if self.active_id in ids:
                state = gui_state_from_dict(self.copied_edits)
                state.gui_only.display = collect_gui_state(widgets=self.widgets).gui_only.display
                self.controller.restoring = True
                blockers = [QtCore.QSignalBlocker(obj) for obj in self.editor.findChildren(QtCore.QObject)]
                try:
                    apply_gui_state(state, widgets=self.widgets)
                finally:
                    del blockers
                    self.controller.restoring = False
                self.saved = None
                self.open_photo(self.active_id, force=True)
            self.window.statusBar().showMessage(f'Parameters pasted to {len(ids)} photos')
        except (ValueError, sqlite3.Error) as exc:
            W.QMessageBox.warning(self, 'Paste parameters', str(exc))

    def change_execution_backend(self, *_args):
        backend = self.execution_combo.currentData()
        self.store.set_state('execution_backend', backend)
        self.execution_status.setText('CPU' if backend == 'cpu' else 'CUDA · checked on first calculation')
        self.execution_status.setToolTip(self.execution_status.text())
        self.controller.set_execution_backend(backend)

    @QtCore.Slot(int, str)
    def update_execution_status(self, run_id, status):
        if run_id != self.controller.scan_run_id or self.closing or self.closed:
            return
        if getattr(self.controller, '_simulation_token', None) != self.controller.state_token():
            return
        self.execution_status.setToolTip(status)
        self.execution_status.setText(self.execution_status.fontMetrics().elidedText(
            status, QtCore.Qt.ElideRight, 330))

    def resize_thumbnails(self, width):
        height = round(width * .75)
        self.strip.setIconSize(QtCore.QSize(width, height))
        self.strip.setGridSize(QtCore.QSize(width + 24, height + 38))
        self.store.set_state('thumbnail_size', width)

    def save_strip_height(self, *_args):
        self.store.set_state('filmstrip_height', self.workspace_split.sizes()[1])

    @QtCore.Slot(int, str, int, int)
    def scan_progress(self, run_id, stage, completed, total):
        if (run_id != self.controller.scan_run_id or self.closed or self.closing
                or self.controller._active_simulation_label != 'Scan'):
            return
        if self.controller.restoring or self.controller._simulation_token != self.controller.state_token():
            self.finish_scan('Scan result no longer matches the selected photo/settings')
            return
        if self.scan_started is None:
            self.scan_started = monotonic()
            self.scan_timer.start()
        names = {
            'preprocess': 'Preparing image', 'filming.expose': 'Film exposure',
            'filming.develop': 'Film development', 'printing.expose': 'Print exposure',
            'printing.develop': 'Print development', 'scanning.scan_film': 'Scanning film',
            'scanning.scan_print': 'Scanning print',
        }
        self.scan_stage = 'SCAN · ' + names.get(stage, stage)
        self.scan_bar.setVisible(True)
        self.scan_bar.setRange(0, total)
        self.scan_bar.setValue(completed)
        self.scan_bar.setFormat('%v / %m steps' if total else 'Preparing…')
        self.update_scan_elapsed()

    def update_scan_elapsed(self):
        if self.scan_started is not None:
            elapsed = int(monotonic() - self.scan_started)
            self.scan_label.setText(f'{self.scan_stage} · {elapsed // 60:02d}:{elapsed % 60:02d}')

    def finish_scan(self, message, success=False):
        if self.scan_started is None:
            return
        self.scan_timer.stop()
        self.scan_stage = message
        self.update_scan_elapsed()
        self.scan_started = None
        if success:
            self.scan_bar.setRange(0, 1)
            self.scan_bar.setValue(1)
            self.scan_bar.setFormat('Complete')
        else:
            self.scan_bar.setVisible(False)

    def _list(self, width, height):
        view = W.QListWidget()
        view.setViewMode(W.QListView.IconMode)
        view.setResizeMode(W.QListView.Adjust)
        view.setMovement(W.QListView.Static)
        view.setIconSize(QtCore.QSize(width, height))
        view.setGridSize(QtCore.QSize(width + 24, height + 42))
        view.setSpacing(6)
        view.setWordWrap(False)
        return view

    def _task(self, key, function, success, failure):
        task = Task(key, function)
        task.signals.finished.connect(success)
        task.signals.failed.connect(failure)
        task.signals.finished.connect(self.task_done)
        task.signals.failed.connect(self.task_done)
        self.tasks[key] = task
        self.pool.start(task)

    def task_done(self, key, _result):
        self.tasks.pop(key, None)

    def refresh(self):
        selected = self.selected_id()
        self.grid.blockSignals(True)
        self.strip.blockSignals(True)
        self.grid.clear()
        self.strip.clear()
        self.items.clear()
        self.pending_thumbnails.clear()
        for row in self.store.photos():
            photo_id, path = row['id'], row['path']
            missing = not Path(path).is_file()
            pair = []
            for view in (self.grid, self.strip):
                item = W.QListWidgetItem(('Missing · ' if missing else '') + Path(path).name)
                item.setData(QtCore.Qt.UserRole, photo_id)
                item.setToolTip(path + ('\nOriginal missing — use Locate original.' if missing else ''))
                item.setIcon(self.style().standardIcon(W.QStyle.SP_FileIcon))
                view.addItem(item)
                pair.append(item)
            self.items[photo_id] = pair
            if not missing:
                self.pending_thumbnails.append((photo_id, path))
        target = selected if selected in self.items else self.active_id
        if target in self.items:
            self.grid.setCurrentItem(self.items[target][0])
            self.strip.setCurrentItem(self.items[target][1])
        self.grid.blockSignals(False)
        self.strip.blockSignals(False)
        self.rebuild_folders()
        self.filter(self.search.text())
        self.next_thumbnail()

    def next_thumbnail(self):
        if self.thumbnail_running or not self.pending_thumbnails or self.closing:
            return
        photo_id, path = self.pending_thumbnails.popleft()
        self.thumbnail_running = True
        self._task(('thumbnail', photo_id, path), lambda: thumbnail(path, self.cache),
                   self.thumbnail_ready, self.thumbnail_failed)

    def thumbnail_ready(self, key, result):
        row = self.store.photo(key[1])
        if row is not None and row['path'] == key[2]:
            for item in self.items.get(key[1], []):
                item.setIcon(QtGui.QIcon(result))
        self.thumbnail_running = False
        QtCore.QTimer.singleShot(0, self.next_thumbnail)

    def thumbnail_failed(self, key, message):
        for item in self.items.get(key[1], []):
            item.setToolTip(f'{key[2]}\nPreview unavailable: {message}')
            item.setText('Preview unavailable · ' + Path(key[2]).name)
        self.thumbnail_running = False
        QtCore.QTimer.singleShot(0, self.next_thumbnail)

    def rebuild_folders(self):
        self.folders.blockSignals(True)
        self.folders.clear()
        self.folder_items.clear()
        all_item = W.QTreeWidgetItem(['All Photos  (' + str(len(self.items)) + ')'])
        all_item.setData(0, QtCore.Qt.UserRole, '')
        self.folders.addTopLevelItem(all_item)
        self.folder_items[''] = all_item
        records = self.store.folders()
        paths = {row['path_key']: row['path'] for row in records}
        for key in sorted(paths, key=lambda value: (len(Path(value).parts), value)):
            parent = next((str(p) for p in Path(key).parents if str(p) in self.folder_items), '')
            count = len(self.store.photos_in_folder(key))
            missing = not Path(paths[key]).is_dir()
            item = W.QTreeWidgetItem([('Missing · ' if missing else '') + Path(paths[key]).name + f'  ({count})'])
            item.setData(0, QtCore.Qt.UserRole, key)
            item.setToolTip(0, paths[key])
            if parent:
                self.folder_items[parent].addChild(item)
            else:
                self.folders.addTopLevelItem(item)
            self.folder_items[key] = item
        if self.current_folder not in self.folder_items:
            self.current_folder = ''
        self.folders.setCurrentItem(self.folder_items[self.current_folder])
        self.folders.expandAll()
        self.folders.blockSignals(False)

    def visible_ids(self):
        return [row['id'] for row in self.store.photos_in_folder(self.current_folder)]

    def filter(self, text):
        folder_ids = set(self.visible_ids())
        visible = 0
        for photo_id, (item, strip_item) in self.items.items():
            strip_item.setHidden(photo_id not in folder_ids)
            row = self.store.photo(photo_id)
            match = photo_id in folder_ids and text.casefold() in Path(row['path']).name.casefold()
            item.setHidden(not match)
            visible += int(match)
        self.count.setText(f'{visible} / {len(folder_ids)} photos')

    def folder_changed(self, item, previous):
        if item is None:
            return
        if not self.save_active():
            self.folders.blockSignals(True)
            self.folders.setCurrentItem(previous)
            self.folders.blockSignals(False)
            return
        self.cancel_load()
        self.current_folder = item.data(0, QtCore.Qt.UserRole)
        self.store.set_state('folder', self.current_folder)
        self.search.clear()
        self.filter('')
        chosen = self.folder_photo()
        self.set_selected(chosen)
        if self.stack.currentIndex() == 1:
            self.develop_selected(chosen)

    def folder_photo(self):
        rows = self.store.photos_in_folder(self.current_folder)
        available = [row['id'] for row in rows if Path(row['path']).is_file()]
        last = self.store.last_photo(self.current_folder)
        return last if last in available else next(iter(available), None)

    def set_selected(self, photo_id):
        self.store.set_state('selected_photo', photo_id if photo_id is not None else '')
        self.grid.blockSignals(True)
        self.strip.blockSignals(True)
        self.grid.setCurrentItem(self.items[photo_id][0] if photo_id in self.items else None)
        self.strip.setCurrentItem(self.items[photo_id][1] if photo_id in self.items else None)
        self.grid.blockSignals(False)
        self.strip.blockSignals(False)

    def switch_module(self, index):
        if not self.save_active():
            self.modules.blockSignals(True)
            self.modules.setCurrentIndex(self.stack.currentIndex())
            self.modules.blockSignals(False)
            return
        self.cancel_load()
        self.stack.setCurrentIndex(index)
        self.histogram.setVisible(index == 1)
        self.store.set_state('module', index)
        if index == 1:
            chosen = self.selected_id()
            if chosen not in self.visible_ids():
                chosen = self.folder_photo()
            self.develop_selected(chosen)

    def develop_selected(self, photo_id):
        if photo_id is None:
            self.editor_stack.setCurrentIndex(0)
            self.editor.setEnabled(False)
        else:
            self.open_photo(photo_id)

    def selected_id(self):
        item = self.grid.currentItem()
        return item.data(QtCore.Qt.UserRole) if item else None

    def select_grid(self, item, _previous):
        if item:
            self.store.set_state('selected_photo', item.data(QtCore.Qt.UserRole))
            self.strip.blockSignals(True)
            self.strip.setCurrentItem(self.items[item.data(QtCore.Qt.UserRole)][1], QtCore.QItemSelectionModel.NoUpdate)
            self.strip.blockSignals(False)

    def select_strip(self, item, _previous):
        if item:
            photo_id = item.data(QtCore.Qt.UserRole)
            self.grid.setCurrentItem(self.items[photo_id][0])
            if self.stack.currentIndex() == 1:
                self.open_photo(photo_id)

    def choose_files(self):
        settings = QtCore.QSettings('spektrafilm-Table', 'imports')
        paths, _ = W.QFileDialog.getOpenFileNames(self, 'Select photos to preview', settings.value('files_directory', ''),
                    'Photos (' + ' '.join('*' + ext for ext in sorted(IMAGE_EXTENSIONS)) + ')')
        if paths:
            settings.setValue('files_directory', str(Path(paths[0]).parent))
            self.show_import_preview(paths)

    def choose_folder(self):
        self.show_import_preview()

    def show_import_preview(self, paths=None):
        # Hidden dialogs are retained only until their outstanding workers finish.
        for previous in self.dialogs[:]:
            if previous.finished_preview and not previous.tasks:
                self.dialogs.remove(previous)
                previous.deleteLater()
        dialog = ImportPreview(self, existing_paths=[row['path_key'] for row in self.store.photos()],
                               cache=self.cache, paths=paths)
        self.dialogs.append(dialog)
        if dialog.exec() == W.QDialog.Accepted:
            self.import_target = dialog.source_folder or str(Path(dialog.selected_paths[0]).parent)
            for source in dialog.sources:
                if Path(source).is_dir():
                    self.store.register_folder(source)
            self.store.register_folder(self.import_target)
            self.import_paths(dialog.selected_paths)

    def import_paths(self, paths):
        self.import_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.progress.setText('Discovering photos…')
        self._task(('discover', object()), lambda: list(discover_photos(paths)),
                   self.discovered, self.import_failed)

    def discovered(self, _key, paths):
        self.import_queue = deque(paths)
        self.import_total = len(paths)
        self.import_added = 0
        self.import_processed = 0
        self.import_batch()

    def import_batch(self):
        if self.closing:
            return
        try:
            for _ in range(min(50, len(self.import_queue))):
                _, added = self.store.add(self.import_queue.popleft())
                self.import_added += added
                self.import_processed += 1
        except (OSError, sqlite3.Error) as exc:
            self.import_failed(None, str(exc))
            return
        self.progress.setText(f'Imported {self.import_processed}/{self.import_total} · {self.import_added} new')
        if self.import_queue:
            QtCore.QTimer.singleShot(0, self.import_batch)
        else:
            self.import_button.setEnabled(True)
            self.folder_button.setEnabled(True)
            if self.import_target is not None:
                from spektrafilm_gui.library_store import canonical_path
                self.current_folder = canonical_path(self.import_target)
                self.store.set_state('folder', self.current_folder)
                self.import_target = None
                self.modules.setCurrentIndex(0)
            self.refresh()

    def import_failed(self, _key, message):
        self.import_target = None
        self.progress.setText('Import failed: ' + message)
        self.import_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.refresh()

    def import_and_open(self, path):
        if not self.save_active():
            return
        try:
            photo_id, _ = self.store.add(path)
        except (OSError, sqlite3.Error) as exc:
            W.QMessageBox.warning(self, 'Import photo', str(exc))
            return
        from spektrafilm_gui.library_store import canonical_path
        self.current_folder = canonical_path(Path(path).parent)
        self.store.set_state('folder', self.current_folder)
        self.refresh()
        self.open_photo(photo_id, force=True)

    def edits(self):
        data = gui_state_to_dict(collect_gui_state(widgets=self.widgets))
        data.pop('display', None)
        return data

    def save_active(self):
        if self.active_id is None or self.controller.restoring:
            return True
        data = self.edits()
        signature = (json.dumps(data, sort_keys=True), self.controller.rotation)
        if signature == self.saved:
            return True
        try:
            self.store.save_edits(self.active_id, data, self.controller.rotation)
        except (OSError, sqlite3.Error) as exc:
            self.window.statusBar().showMessage('Could not save photo edits: ' + str(exc))
            return False
        self.saved = signature
        return True

    def autosave(self):
        self.save_active()

    def open_photo(self, photo_id, force=False):
        if self.closing or not self.save_active():
            return
        self.modules.blockSignals(True)
        self.modules.setCurrentIndex(1)
        self.modules.blockSignals(False)
        self.stack.setCurrentIndex(1)
        self.histogram.show()
        self.store.set_state('module', 1)
        if photo_id == self.active_id and not force and not self.controller.restoring:
            self.editor_stack.setCurrentIndex(1)
            self.editor.setEnabled(True)
            self.store.remember_photo(self.current_folder, photo_id)
            return
        row = self.store.photo(photo_id)
        if row is None:
            return
        if not Path(row['path']).is_file():
            W.QMessageBox.warning(self, 'Original missing', 'Use Locate original in the library to reconnect this photo.')
            return
        try:
            data = json.loads(row['edits']) if row['edits'] else dict(self.defaults)
            # Reprocessing the active RAW uses its latest controls, not old startup defaults.
            if photo_id == self.active_id:
                data = self.edits()
            data['display'] = gui_state_to_dict(collect_gui_state(widgets=self.widgets))['display']
            state = gui_state_from_dict(data)
        except (ValueError, TypeError, KeyError) as exc:
            W.QMessageBox.warning(self, 'Photo settings', f'Could not read saved settings: {exc}')
            return
        self.widgets.load_raw.pick_white_balance.setChecked(False)
        self.histogram.set_image(None)
        self.load_serial += 1
        serial = self.load_serial
        self.controller.restoring = True
        self.controller.photo_revision += 1
        self.editor.setEnabled(False)
        self.pending_load = (photo_id, row['path'], state, row['rotation'])
        self.window.statusBar().showMessage('Loading ' + Path(row['path']).name + '…')
        self.progress.setText('Loading ' + Path(row['path']).name + '…')
        self._task(('load', serial), lambda: decode_photo(row['path'], state), self.loaded, self.load_failed)

    def loaded(self, key, image):
        if key[1] != self.load_serial or self.closing:
            return
        photo_id, path, state, rotation = self.pending_load
        old_state = collect_gui_state(widgets=self.widgets)
        old_image = self.controller._current_input_image
        old_preview = self.controller._current_preview_image
        old_daylight = self.controller._daylight_image
        blockers = [QtCore.QSignalBlocker(obj) for obj in self.editor.findChildren(QtCore.QObject)]
        try:
            if isinstance(image, dict) and image.get('camera_balance') and state.gui_only.load_raw.white_balance == 'as_shot':
                state.gui_only.load_raw.temperature, state.gui_only.load_raw.tint = image['camera_balance']
            apply_gui_state(state, widgets=self.widgets)
            self.controller._base_preview_cache = None
            bases = image if isinstance(image, dict) else {'as_shot': image, 'daylight': image}
            self.controller._camera_balance = bases.get('camera_balance')
            self.widgets.load_raw.temperature.setToolTip('Camera-derived equivalent temperature (approximate Kelvin); as-shot rendering uses the original camera white balance.')
            self.controller._daylight_image = np.rot90(bases['daylight'], rotation)
            self.controller._set_or_add_input_stack(np.rot90(bases['as_shot'], rotation))
        except Exception as exc:
            apply_gui_state(old_state, widgets=self.widgets)
            self.controller._daylight_image = old_daylight
            self.controller._current_input_image = old_image
            self.controller._current_preview_image = old_preview
            if old_image is not None:
                self.controller._set_or_add_input_stack(old_image)
            self.load_failed(key, str(exc))
            return
        finally:
            del blockers
        self.active_id = photo_id
        self.store.remember_photo(self.current_folder, photo_id)
        self.store.remember_photo('', photo_id)
        self.editor_stack.setCurrentIndex(1)
        self.controller._current_input_path = path
        self.controller.rotation = rotation
        self.controller._next_runtime_digest_applies_stock_specifics = True
        self.widgets.filepicker.file_path.setText(path)
        self.widgets.load_raw.set_path(path if Path(path).suffix.lower() in RAW_EXTENSIONS else '')
        self.controller.restoring = False
        self.editor.setEnabled(True)
        self.saved = None
        self.save_active()
        if photo_id in self.items:
            self.grid.setCurrentItem(self.items[photo_id][0])
        self.window.statusBar().showMessage('Loaded ' + Path(path).name)
        self.progress.setText('Double-click a photo to edit.')
        self.update_histogram()
        self.controller.request_auto_preview()

    def load_failed(self, key, message):
        if key[1] != self.load_serial or self.closing:
            return
        self.controller.restoring = False
        self.editor.setEnabled(self.active_id is not None)
        self.progress.setText('Load failed: ' + message)
        self.window.statusBar().showMessage('Load failed: ' + message)
        W.QMessageBox.warning(self, 'Could not open photo', message)

    def show_library(self):
        self.modules.setCurrentIndex(0)

    def remove_selected(self):
        photo_id = self.selected_id()
        if photo_id is None or not self.save_active():
            return
        if W.QMessageBox.question(self, 'Remove from library', 'Remove this photo from the catalog? The original file will not be deleted.') != W.QMessageBox.Yes:
            return
        self.cancel_load()
        try:
            self.store.remove(photo_id)
        except sqlite3.Error as exc:
            W.QMessageBox.warning(self, 'Remove from library', str(exc))
            return
        if photo_id == self.active_id:
            self.active_id = None
            self.controller._current_input_path = None
            self.controller._daylight_image = None
            self.controller._base_preview_cache = None
            self.controller._current_input_image = None
            self.controller._current_preview_image = None
            self.controller.photo_revision += 1
            self.editor_stack.setCurrentIndex(0)
            self.editor.setEnabled(False)
        self.refresh()

    def cancel_load(self):
        self.load_serial += 1
        self.controller.restoring = False
        self.editor.setEnabled(self.active_id is not None)

    def relocate_selected(self):
        photo_id = self.selected_id()
        if photo_id is None or not self.save_active():
            return
        path, _ = W.QFileDialog.getOpenFileName(self, 'Locate original')
        if not path:
            return
        try:
            self.store.relocate(photo_id, path)
        except (ValueError, sqlite3.Error) as exc:
            W.QMessageBox.warning(self, 'Locate original', str(exc))
            return
        self.cancel_load()
        if photo_id == self.active_id:
            from spektrafilm_gui.library_store import canonical_path
            self.current_folder = canonical_path(Path(path).parent)
            self.store.set_state('folder', self.current_folder)
        self.refresh()
        if photo_id == self.active_id:
            self.open_photo(photo_id, force=True)

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() == QtCore.QEvent.Close and not self.closed:
            if not self.save_active():
                event.ignore()
                return True
            self.closing = True
            self.timer.stop()
            self.scan_timer.stop()
            self.cache_timer.stop()
            self.controller._wb_timer.stop()
            self.save_strip_height()
            self.pending_thumbnails.clear()
            for dialog in self.dialogs:
                if not dialog.finished_preview:
                    dialog.reject()
            if self.tasks or any(dialog.tasks for dialog in self.dialogs) or self.controller._active_simulation_worker is not None:
                self.window.statusBar().showMessage('Finishing background work before closing…')
                QtCore.QTimer.singleShot(200, self.window.close)
                event.ignore()
                return True
            settings = QtCore.QSettings('spektrafilm-Table', 'library')
            settings.setValue('geometry', self.window.saveGeometry())
            settings.setValue('display', json.dumps(gui_state_to_dict(collect_gui_state(widgets=self.widgets))['display']))
            simulator = self.controller._runtime_simulator
            if simulator is not None and hasattr(simulator, 'close'):
                simulator.close()
            self.store.close()
            self.closed = True
        return super().eventFilter(watched, event)
