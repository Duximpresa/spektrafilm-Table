"""Non-destructive import selection with asynchronous folder previews."""
from collections import deque
from pathlib import Path
from threading import Event

from qtpy import QtCore, QtGui, QtWidgets as W

from spektrafilm_gui.library_store import canonical_path, discover_photos
from spektrafilm_gui.library_workers import Task, thumbnail


class ImportPreview(W.QDialog):
    def __init__(self, parent, *, existing_paths, cache, paths=None):
        super().__init__(parent)
        self.setWindowTitle('Import photos')
        self.resize(1040, 700)
        self.settings = QtCore.QSettings('spektrafilm-Table', 'imports')
        self.cache = cache
        self.existing = set(existing_paths)
        self.sources = list(paths or [])
        self.source_folder = ''
        self.selected_paths = []
        self.serial = 0
        self.cancel = Event()
        self.tasks = {}
        self.queue = deque()
        self.thumb_busy = False
        self.finished_preview = False
        self.scanning = False
        self.pool = QtCore.QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.rows = {}
        self.file_model = W.QFileSystemModel(self)
        self.file_model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.Drives)
        self.file_model.setRootPath('')
        self.tree = W.QTreeView()
        self.tree.setModel(self.file_model)
        for column in range(1, self.file_model.columnCount()):
            self.tree.hideColumn(column)
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.tree.selectionModel().selectionChanged.connect(self.folders_changed)
        self.recursive = W.QCheckBox('Include subfolders')
        self.recursive.setStyleSheet('QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #777; } '
                                    'QCheckBox::indicator:checked { background-color: #f5a16e; }')
        self.recursive.setChecked(self.settings.value('recursive', True, type=bool))
        self.recursive.toggled.connect(lambda _: self.scan())
        self.preview_enabled = W.QCheckBox('Show photo previews')
        self.preview_enabled.setChecked(self.settings.value('previews', True, type=bool))
        self.preview_enabled.toggled.connect(self.preview_toggled)
        self.path_label = W.QLabel('Select a source folder on the left')
        self.path_label.setWordWrap(True)
        self.grid = W.QListWidget()
        self.grid.setViewMode(W.QListView.IconMode)
        self.grid.setResizeMode(W.QListView.Adjust)
        self.grid.setMovement(W.QListView.Static)
        self.grid.setIconSize(QtCore.QSize(140, 105))
        self.grid.setGridSize(QtCore.QSize(175, 145))
        self.grid.itemChanged.connect(self.update_count)
        self.status = W.QLabel('No folder selected.')
        self.status.setWordWrap(True)
        all_button, none_button = W.QPushButton('Select all'), W.QPushButton('Select none')
        all_button.clicked.connect(lambda: self.check_all(True))
        none_button.clicked.connect(lambda: self.check_all(False))
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Cancel)
        self.import_button = buttons.addButton('Import selected', W.QDialogButtonBox.AcceptRole)
        self.import_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right = W.QWidget()
        layout = W.QVBoxLayout(right)
        layout.addWidget(self.path_label)
        options = W.QHBoxLayout()
        for widget in (self.recursive, self.preview_enabled, all_button, none_button):
            options.addWidget(widget)
        layout.addLayout(options)
        layout.addWidget(self.grid, 1)
        layout.addWidget(self.status)
        layout.addWidget(buttons)
        split = W.QSplitter()
        split.addWidget(self.tree)
        split.addWidget(right)
        split.setSizes([250, 790])
        W.QVBoxLayout(self).addWidget(split)
        if paths:
            self.tree.setVisible(False)
            self.recursive.setVisible(False)
            self.path_label.setText(f'{len(paths)} selected files')
            self.scan()

        else:
            saved = self.settings.value('folders', [], type=list)
            for folder in saved:
                index = self.file_model.index(folder)
                if index.isValid():
                    self.tree.selectionModel().select(index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
                    self.tree.scrollTo(index)
                    parent_index = index.parent()
                    while parent_index.isValid():
                        self.tree.expand(parent_index)
                        parent_index = parent_index.parent()

    def preview_toggled(self, enabled):
        self.settings.setValue('previews', enabled)
        self.queue.clear()
        if not enabled:
            for item in self.rows.values():
                item.setIcon(self.style().standardIcon(W.QStyle.SP_FileIcon))
        if enabled:
            self.queue.extend(self.rows)
            self.next_thumbnail()
        self.update_count()

    def folders_changed(self, *_args):
        self.sources = [self.file_model.filePath(index) for index in self.tree.selectionModel().selectedRows(0)]
        self.source_folder = self.sources[0] if self.sources else ''
        self.settings.setValue('folders', self.sources)
        self.path_label.setText('\n'.join(self.sources) or 'Ctrl-click to select folders')
        self.scan()

    def folder_clicked(self, index):
        path = self.file_model.filePath(index)
        if path and Path(path).is_dir():
            self.source_folder = path
            self.sources = [path]
            self.path_label.setText(path)
            self.scan()

    def _start(self, key, function, success, failure):
        task = Task(key, function)
        task.signals.finished.connect(success)
        task.signals.failed.connect(failure)
        task.signals.finished.connect(self._done)
        task.signals.failed.connect(self._done)
        self.tasks[key] = task
        self.pool.start(task)

    def _done(self, key, _result):
        self.tasks.pop(key, None)

    def scan(self):
        if self.finished_preview:
            return
        self.cancel.set()
        self.cancel = Event()
        token = self.cancel
        self.serial += 1
        self.queue.clear()
        self.grid.clear()
        self.rows.clear()
        self.scanning = True
        self.import_button.setEnabled(False)
        self.status.setText('Scanning folder…')
        sources, recursive = list(self.sources), self.recursive.isChecked()
        self.settings.setValue('recursive', recursive)

        def discover():
            found = []
            seen = set()
            for path in discover_photos(sources, recursive=recursive):
                if token.is_set():
                    break
                key = canonical_path(path)
                if key not in seen:
                    seen.add(key)
                    found.append(path)
            return found
        self._start(('scan', self.serial), discover, self.scanned, self.scan_failed)

    def scanned(self, key, paths):
        if key[1] != self.serial or self.finished_preview:
            return
        self.scanning = False
        self.grid.blockSignals(True)
        for path in paths:
            exists = canonical_path(path) in self.existing
            item = W.QListWidgetItem(Path(path).name + (' · Imported' if exists else ''))
            item.setData(QtCore.Qt.UserRole, path)
            item.setToolTip(path)
            item.setIcon(self.style().standardIcon(W.QStyle.SP_FileIcon))
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked if exists else QtCore.Qt.Checked)
            if exists:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            self.grid.addItem(item)
            self.rows[path] = item
            if self.preview_enabled.isChecked():
                self.queue.append(path)
        self.grid.blockSignals(False)
        self.update_count()
        self.next_thumbnail()

    def scan_failed(self, key, message):
        if key[1] == self.serial and not self.finished_preview:
            self.scanning = False
            self.status.setText('Could not read folder: ' + message)
            self.import_button.setEnabled(False)


    def check_all(self, selected):
        self.grid.blockSignals(True)
        for item in self.rows.values():
            if item.flags() & QtCore.Qt.ItemIsEnabled:
                item.setCheckState(QtCore.Qt.Checked if selected else QtCore.Qt.Unchecked)
        self.grid.blockSignals(False)
        self.update_count()

    def update_count(self, *_args):
        count = len(self.checked_paths())
        self.import_button.setEnabled(not self.scanning and count > 0)
        if not self.scanning:
            if not self.rows:
                self.status.setText('No supported photos found in this folder.')
            else:
                pending = len(self.queue) + int(self.thumb_busy)
                self.status.setText(f'{count} selected / {len(self.rows)} photos · {pending} previews pending'
                                    + (' · No photos selected for import.' if count == 0 else ''))

    def checked_paths(self):
        return [path for path, item in self.rows.items()
                if item.checkState() == QtCore.Qt.Checked and item.flags() & QtCore.Qt.ItemIsEnabled]

    def next_thumbnail(self):
        if self.thumb_busy or not self.queue or self.finished_preview or not self.preview_enabled.isChecked():
            return
        path = self.queue.popleft()
        self.thumb_busy = True
        self._start(('thumb', self.serial, path), lambda: thumbnail(path, self.cache),
                    self.thumbnail_ready, self.thumbnail_failed)

    def thumbnail_ready(self, key, result):
        if key[1] == self.serial and not self.finished_preview and self.preview_enabled.isChecked() and key[2] in self.rows:
            self.rows[key[2]].setIcon(QtGui.QIcon(result))
        self.thumbnail_finished()

    def thumbnail_failed(self, key, message):
        if key[1] == self.serial and not self.finished_preview and self.preview_enabled.isChecked() and key[2] in self.rows:
            item = self.rows[key[2]]
            item.setText('Preview unavailable · ' + Path(key[2]).name)
            item.setToolTip(key[2] + '\n' + message)
        self.thumbnail_finished()

    def thumbnail_finished(self):
        self.thumb_busy = False
        if not self.finished_preview:
            self.update_count()
            QtCore.QTimer.singleShot(0, self.next_thumbnail)

    def accept(self):
        if self.scanning or not self.checked_paths():
            return
        self.selected_paths = self.checked_paths()
        super().accept()

    def done(self, result):
        self.finished_preview = True
        self.serial += 1
        self.cancel.set()
        self.queue.clear()
        super().done(result)
