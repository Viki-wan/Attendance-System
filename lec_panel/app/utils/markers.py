"""
Markers (Phase 7c)

A marker is a small system-owned ``settings`` row that remembers "this
operation was already done for this term", so a one-off job (the semester
rollover now, the yearly promotion in 7d) cannot run twice for the same term.

- Key ``marker_<name>``, ``is_system = 1``. The settings page never lists these
  and ``SettingsAdminService`` refuses to edit system rows, so an admin cannot
  change one by accident. Keys never start with ``academic_calendar_``.
- A term is written ``<academic year>:<semester>`` (``2026:2`` = 2026/27
  semester 2). 7d can store a bare academic year the same way.
- Reading never raises (an unreadable row reads as "no marker").
- Writing is a compare-and-swap done INSIDE the caller's transaction and never
  commits: ``swap_marker(name, old, new)`` succeeds only if the stored value is
  still what the caller saw. The caller commits (or rolls back) the marker
  together with the data it protects, so they stand or fall together.
"""

import logging
from datetime import datetime

from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)

MARKER_PREFIX = 'marker_'


def marker_key(name):
    return f"{MARKER_PREFIX}{name}"


def format_term(academic_year, semester=None):
    """(2026, 2) -> '2026:2'; (2026, None) -> '2026'."""
    if semester is None:
        return str(int(academic_year))
    return f"{int(academic_year)}:{int(semester)}"


def parse_term(value):
    """'2026:2' -> (2026, 2); '2026' -> (2026, None); anything else -> None."""
    try:
        parts = str(value).strip().split(':')
        if len(parts) == 1:
            return (int(parts[0]), None)
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
    except (TypeError, ValueError):
        pass
    return None


def read_marker_info(name):
    """``{'value', 'description', 'updated_at'}`` of a marker, or None. Never raises."""
    try:
        row = db.session.execute(text(
            "SELECT setting_value, description, updated_at FROM settings "
            "WHERE setting_key = :k"), {'k': marker_key(name)}).first()
        if row is None or row[0] in (None, ''):
            return None
        return {'value': str(row[0]).strip(), 'description': row[1], 'updated_at': row[2]}
    except Exception as e:
        logger.error(f"Could not read marker {name}: {e}")
        return None


def read_marker(name):
    info = read_marker_info(name)
    return info['value'] if info else None


def swap_marker(name, old, new, description=''):
    """
    Compare-and-swap, no commit. ``old`` is the value the caller saw (None = no
    row). Returns True when the marker now holds ``new``, False when somebody
    changed it first (the caller must then roll back).
    """
    stamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    params = {'k': marker_key(name), 'new': str(new), 'd': description, 'ts': stamp}
    if old is None:
        result = db.session.execute(text("""
            INSERT OR IGNORE INTO settings
                (setting_key, setting_value, description, category, is_system, created_at, updated_at)
            VALUES (:k, :new, :d, 'system', 1, :ts, :ts)
        """), params)
    else:
        params['old'] = str(old)
        result = db.session.execute(text("""
            UPDATE settings
               SET setting_value = :new, description = :d, category = 'system',
                   is_system = 1, updated_at = :ts
             WHERE setting_key = :k AND setting_value = :old
        """), params)
    return result.rowcount == 1