"""Owned thumbnail cache: never delete originals or catalog files."""
from pathlib import Path
import re
from qtpy import QtWidgets as W


def cache_files(directory):
    root = Path(directory).resolve()
    if not root.is_dir() or Path(directory).is_symlink():
        return []
    return [p for p in root.iterdir() if re.fullmatch(r'[0-9a-f]{64}\.jpg', p.name)
            and p.is_file() and not p.is_symlink()]


def cache_size(directory):
    return sum(p.stat().st_size for p in cache_files(directory))


def clean_cache(directory, limit=0):
    files = sorted(cache_files(directory), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    for path in files:
        if total <= limit:
            break
        size = path.stat().st_size
        path.unlink()
        total -= size
    return total


class CacheSettings(W.QDialog):
    def __init__(self, library):
        super().__init__(library)
        self.library = library
        self.setWindowTitle('Settings · Cache')
        form = W.QFormLayout(self)
        self.path = W.QLineEdit(str(library.cache))
        self.path.setReadOnly(True)
        choose = W.QPushButton('Choose cache directory…')
        choose.clicked.connect(self.choose)
        self.size = W.QLabel()
        self.auto = W.QCheckBox('Automatically remove oldest thumbnails above limit')
        self.auto.setChecked(library.store.get_state('cache_auto', '1') == '1')
        self.limit = W.QSpinBox()
        self.limit.setRange(16, 102400)
        self.limit.setSuffix(' MiB')
        self.limit.setValue(int(library.store.get_state('cache_limit_mb', '1024')))
        clear = W.QPushButton('Clear cache now')
        clear.clicked.connect(self.clear)
        save = W.QPushButton('Save settings')
        save.clicked.connect(self.save)
        for widget in (self.path, choose, self.size, self.auto, self.limit, clear, save):
            form.addRow(widget)
        self.refresh()

    def refresh(self):
        self.size.setText(f'Thumbnail disk cache: {cache_size(self.path.text()) / 1024**2:.2f} MiB')

    def choose(self):
        folder = W.QFileDialog.getExistingDirectory(self, 'Choose cache parent directory', self.path.text())
        if folder:
            self.path.setText(str(Path(folder) / 'spektrafilm-thumbnails'))
            self.refresh()

    def clear(self):
        if self.library.tasks or any(d.tasks for d in self.library.dialogs):
            W.QMessageBox.information(self, 'Cache busy', 'Wait for image loading/import previews to finish, then clear the cache.')
            return
        try:
            clean_cache(self.path.text())
            self.refresh()
        except OSError as exc:
            W.QMessageBox.warning(self, 'Cache', str(exc))

    def save(self):
        try:
            target = Path(self.path.text())
            target.mkdir(parents=True, exist_ok=True)
            from tempfile import TemporaryFile
            with TemporaryFile(dir=target):
                pass
            self.library.cache = target
            for key, value in (('cache_directory', target), ('cache_auto', int(self.auto.isChecked())),
                               ('cache_limit_mb', self.limit.value())):
                self.library.store.set_state(key, value)
            self.library.trim_cache()
            self.accept()
        except OSError as exc:
            W.QMessageBox.warning(self, 'Cache', str(exc))
