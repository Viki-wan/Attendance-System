"""
Safe database backup (Phase 7c)

Used before any operation that changes data in bulk (the semester rollover now,
the yearly promotion in 7d). Standard library only.

Why SQLite's backup API and not a file copy: the web app has the database open,
and a plain copy of a live SQLite file can capture a half-written state. The
backup API takes a consistent snapshot while the app keeps running.

Rules:
- The copy is written next to the database, in a ``backups`` folder, as
  ``<database file name>.bak-<YYYYmmdd-HHMMSS>-<label>``.
- The name is reserved with an exclusive create, so an earlier backup is NEVER
  overwritten (a second backup in the same second gets a ``-2`` suffix).
- The copy is checked (``PRAGMA integrity_check`` and the same tables as the
  source). If anything fails, the partial file this call created is removed and
  ``BackupError`` is raised, so the caller must not go on to change data.

This is the one place that uses raw ``sqlite3``: the ORM has no backup API.
"""

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_FOLDER = 'backups'


class BackupError(Exception):
    """The backup could not be made or did not pass its check."""


def default_backup_dir(db_path):
    """The folder backups of ``db_path`` go to (not created here)."""
    return Path(db_path).resolve().parent / BACKUP_FOLDER


def _reserve(folder, base):
    """Create an empty file with a name nobody has used; never touches an existing one."""
    for n in range(1, 1000):
        name = base if n == 1 else f"{base}-{n}"
        path = folder / name
        try:
            with open(path, 'xb'):
                pass
            return path
        except FileExistsError:
            continue
    raise BackupError("Could not find a free backup file name")


def _tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def backup_database(db_path, label='backup', backup_dir=None, now=None):
    """
    Write a verified backup. Returns ``{'path', 'name', 'bytes', 'tables'}``.
    Raises ``BackupError`` (and leaves no partial file) when it cannot.
    """
    if not db_path or str(db_path) == ':memory:':
        raise BackupError("The database is not a file, so it cannot be backed up")
    source = Path(db_path).resolve()
    if not source.is_file():
        raise BackupError(f"Database file not found: {source}")

    safe_label = re.sub(r'[^A-Za-z0-9_-]+', '-', str(label)).strip('-') or 'backup'
    stamp = (now or datetime.now()).strftime('%Y%m%d-%H%M%S')
    try:
        folder = Path(backup_dir) if backup_dir else default_backup_dir(source)
        folder.mkdir(parents=True, exist_ok=True)
        dest = _reserve(folder, f"{source.name}.bak-{stamp}-{safe_label}")
    except BackupError:
        raise
    except OSError as e:
        raise BackupError(f"Could not create the backup file: {e}")

    src = dst = None
    try:
        src = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=30)
        dst = sqlite3.connect(str(dest), timeout=30)
        src.backup(dst)
        dst.commit()

        verdict = dst.execute("PRAGMA integrity_check").fetchone()
        if not verdict or verdict[0] != 'ok':
            raise BackupError("The backup copy failed its integrity check")
        source_tables, copy_tables = _tables(src), _tables(dst)
        if source_tables != copy_tables:
            raise BackupError("The backup copy is missing tables")
        for conn in (src, dst):
            conn.close()
        src = dst = None
        return {'path': str(dest), 'name': dest.name,
                'bytes': dest.stat().st_size, 'tables': len(copy_tables)}
    except Exception as e:
        for conn in (src, dst):
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
        try:
            dest.unlink()          # only the file THIS call created
        except OSError:
            pass
        logger.error(f"Database backup failed: {e}")
        if isinstance(e, BackupError):
            raise
        raise BackupError(f"The backup failed: {e}")