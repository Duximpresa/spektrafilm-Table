"""Convenient defaults for GUI parameter files, independent of the working directory."""
from pathlib import Path
from tempfile import TemporaryFile

from qtpy import QtCore


def writable_directory(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        with TemporaryFile(dir=path):
            pass
        return True
    except OSError:
        return False


class PresetPaths:
    def __init__(self, *, settings=None, project_root=None, user_root=None):
        self.settings = settings if settings is not None else QtCore.QSettings('spektrafilm-Table', 'presets')
        self.project_root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
        self.user_root = Path(user_root) if user_root is not None else Path(
            QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.GenericDataLocation)) / 'spektrafilm-Table'

    def default_directory(self):
        root = self.project_root
        if (root / 'pyproject.toml').is_file() and (root / 'src' / 'spektrafilm_gui').is_dir():
            if writable_directory(root / 'presets'):
                return root / 'presets'
        fallback = self.user_root / 'presets'
        if not writable_directory(fallback):
            raise OSError('Could not create a writable presets directory.')
        return fallback

    def initial_directory(self):
        remembered = self.settings.value('last_directory', '')
        if remembered and Path(remembered).is_dir() and writable_directory(Path(remembered)):
            return Path(remembered)
        return self.default_directory()

    def remember(self, filename):
        self.settings.setValue('last_directory', str(Path(filename).resolve().parent))
