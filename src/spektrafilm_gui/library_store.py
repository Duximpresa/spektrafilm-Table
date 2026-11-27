"""Local, non-destructive photo catalog for spektrafilm-Table (GPL-3.0)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

RAW_EXTENSIONS = frozenset('.3fr .arw .cr2 .cr3 .crw .dng .erf .fff .iiq .kdc .mos .mrw .nef .nrw .orf .pef .raf .raw .rw2 .rwl .srw .x3f'.split())
IMAGE_EXTENSIONS = RAW_EXTENSIONS | frozenset('.jpg .jpeg .png .tif .tiff .exr .hdr .bmp .webp .jp2 .ppm .psd'.split())


def canonical_path(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def discover_photos(paths, *, recursive=True):
    """Yield supported files; directory links are never traversed."""
    for value in paths:
        path = Path(value)
        if path.is_dir():
            def report_error(error):
                raise error
            for root, dirs, files in os.walk(path, followlinks=False, onerror=report_error):
                dirs[:] = sorted(d for d in dirs if recursive and not Path(root, d).is_symlink()
                                 and not Path(root, d).is_junction())
                for name in sorted(files):
                    candidate = Path(root, name)
                    if candidate.suffix.lower() in IMAGE_EXTENSIONS:
                        yield str(candidate.resolve())
        elif path.suffix.lower() in IMAGE_EXTENSIONS:
            yield str(path.resolve())


class LibraryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL,
            path_key TEXT NOT NULL UNIQUE, edits TEXT, rotation INTEGER NOT NULL DEFAULT 0)''')
        version = self.connection.execute('PRAGMA user_version').fetchone()[0]
        if version > 2:
            self.connection.close()
            raise ValueError('This catalog was created by a newer version of spektrafilm-Table.')
        with self.connection:
            self.connection.execute('''CREATE TABLE IF NOT EXISTS folders (
                path_key TEXT PRIMARY KEY, path TEXT NOT NULL, last_photo INTEGER)''')
            self.connection.execute('''CREATE TABLE IF NOT EXISTS catalog_state (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
            for row in self.photos():
                self._register_folder(Path(row['path']).parent)
            self.connection.execute('PRAGMA user_version=2')

    def photos(self):
        return self.connection.execute('SELECT * FROM photos ORDER BY id').fetchall()

    def photo(self, photo_id):
        return self.connection.execute('SELECT * FROM photos WHERE id=?', (photo_id,)).fetchone()

    def add(self, path):
        with self.connection:
            self._register_folder(Path(path).resolve().parent)
            cursor = self.connection.execute('INSERT OR IGNORE INTO photos(path,path_key) VALUES (?,?)',
                                             (str(Path(path).resolve()), canonical_path(path)))
        row = self.connection.execute('SELECT id FROM photos WHERE path_key=?', (canonical_path(path),)).fetchone()
        return row['id'], bool(cursor.rowcount)

    def save_edits(self, photo_id, edits, rotation):
        with self.connection:
            self.connection.execute('UPDATE photos SET edits=?,rotation=? WHERE id=?',
                                    (json.dumps(edits), rotation % 4, photo_id))

    def relocate(self, photo_id, path):
        if not Path(path).is_file():
            raise ValueError('The replacement file does not exist.')
        if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError('Unsupported image format.')
        with self.connection:
            self._register_folder(Path(path).resolve().parent)
            self.connection.execute('UPDATE photos SET path=?,path_key=? WHERE id=?',
                                    (str(Path(path).resolve()), canonical_path(path), photo_id))

    def remove(self, photo_id):
        with self.connection:
            self.connection.execute('DELETE FROM photos WHERE id=?', (photo_id,))

    def close(self):
        self.connection.close()

    def _register_folder(self, path):
        self.connection.execute('INSERT OR IGNORE INTO folders(path_key,path) VALUES (?,?)',
                                (canonical_path(path), str(Path(path).resolve())))
        ancestors = list(Path(path).resolve().parents)
        known = {row[0] for row in self.connection.execute('SELECT path_key FROM folders')}
        pending = []
        for ancestor in ancestors:
            if canonical_path(ancestor) in known:
                for intermediate in pending:
                    self.connection.execute('INSERT OR IGNORE INTO folders(path_key,path) VALUES (?,?)',
                                            (canonical_path(intermediate), str(intermediate)))
                break
            pending.append(ancestor)

    def register_folder(self, path):
        with self.connection:
            self._register_folder(path)

    def folders(self):
        return self.connection.execute('SELECT * FROM folders ORDER BY path_key').fetchall()

    def photos_in_folder(self, folder=''):
        if not folder:
            return self.photos()
        parent = Path(canonical_path(folder))
        return [row for row in self.photos() if Path(row['path_key']).is_relative_to(parent)]

    def remember_photo(self, folder, photo_id):
        with self.connection:
            if folder:
                self.connection.execute('UPDATE folders SET last_photo=? WHERE path_key=?',
                                        (photo_id, canonical_path(folder)))
            else:
                self.set_state('all_last_photo', str(photo_id))

    def last_photo(self, folder=''):
        if not folder:
            value = self.get_state('all_last_photo')
            return int(value) if value else None
        row = self.connection.execute('SELECT last_photo FROM folders WHERE path_key=?',
                                      (canonical_path(folder),)).fetchone()
        return row['last_photo'] if row else None

    def set_state(self, key, value):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO catalog_state(key,value) VALUES (?,?)',
                                    (key, str(value)))

    def get_state(self, key, default=''):
        row = self.connection.execute('SELECT value FROM catalog_state WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default
