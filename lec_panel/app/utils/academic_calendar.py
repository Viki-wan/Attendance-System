"""
Academic calendar helpers (Phase 7b).

The whole campus runs on one calendar, so the "current semester" is a single
campus-wide value derived from the date, never a per-student setting. The dates
are set by an admin on /admin/settings, one set of four dates per academic
year (semester 1 start/end, semester 2 start/end). A year nobody has edited
uses the defaults in ``calendar_rules.py`` (semester 1: 1 Sep - 20 Dec,
semester 2: 5 Jan - 30 Apr; the May - Aug holiday counts as semester 2).

This module is the ONE place the rest of the app asks about the calendar:

    get_current_semester(on=None)   -> 1 or 2
    is_in_semester(on=None)         -> True inside a semester window
    semester_window(semester, today=None) -> (start, end)
    get_academic_year(on=None)      -> the year semester 1 started in
    get_year_windows(academic_year) -> {1: (start, end), 2: (start, end)}

The rules themselves live in ``calendar_rules.py`` (no Flask, also used by
tools/relayout_timetable.py). Nothing is read at import time: the stored dates
are looked up at call time and remembered for the rest of the request on
``flask.g`` (cleared when the admin saves), the same way as in the settings
service. A reader never raises: a missing, malformed or inconsistent row, or
a call outside an app context, falls back to the defaults.
"""

import logging
from datetime import date
from typing import Optional

from flask import g, has_app_context

from app.utils import calendar_rules as rules

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Stored windows (call time, memoised per request, never raise)
# ----------------------------------------------------------------------

def _memo():
    if not has_app_context():
        return None
    memo = getattr(g, '_academic_calendar_memo', None)
    if memo is None:
        memo = g._academic_calendar_memo = {}
    return memo


def clear_calendar_memo():
    """Called by the settings service after a save or reset."""
    if has_app_context() and hasattr(g, '_academic_calendar_memo'):
        g._academic_calendar_memo = {}


def get_stored_windows(academic_year):
    """The windows an admin saved for a year, or None (no row, or an unusable one)."""
    try:
        from app.models.settings import Settings
        row = Settings.query.filter_by(setting_key=rules.year_key(academic_year)).first()
        if row is None or row.setting_value in (None, ''):
            return None
        windows = rules.parse_windows(row.setting_value)
        if windows is None or not rules.is_valid_windows(academic_year, windows):
            logger.warning(f"Ignoring unusable academic calendar row for {academic_year}")
            return None
        return windows
    except Exception as e:
        logger.error(f"Could not read the academic calendar for {academic_year}: {e}")
        return None


def get_year_windows(academic_year):
    """Effective windows of an academic year: the saved ones, else the defaults."""
    ay = int(academic_year)
    memo = _memo()
    if memo is not None and ay in memo:
        return memo[ay]
    windows = get_stored_windows(ay) or rules.default_windows(ay)
    if memo is not None:
        memo[ay] = windows
    return windows


# ----------------------------------------------------------------------
# Public entry points
# ----------------------------------------------------------------------

def get_current_semester(on: Optional[date] = None) -> int:
    """
    Campus-wide semester (1 or 2) for a date (default: today).

    Args:
        on: Date to evaluate. Accepts date or datetime. Defaults to today.

    Returns:
        int: 1 or 2. Days inside a window belong to that semester; the days
        between the two semesters count as semester 1 until 31 December and as
        semester 2 from 1 January; the holiday after semester 2 counts as
        semester 2.
    """
    return rules.semester_on(rules.to_date(on), get_year_windows)


def is_in_semester(on: Optional[date] = None) -> bool:
    """True when the date is inside a semester window (not a break or the holiday)."""
    return rules.in_semester_on(rules.to_date(on), get_year_windows)


def get_academic_year(on: Optional[date] = None) -> int:
    """The academic year a date belongs to, named by the year semester 1 starts in."""
    return rules.academic_year_of(rules.to_date(on), get_year_windows)


def semester_window(semester, today: Optional[date] = None):
    """
    ``(start, end)`` dates of the window of ``semester`` that contains ``today``
    or is the next one to begin.
    """
    return rules.semester_window(semester, rules.to_date(today), get_year_windows)


def describe_date(on: Optional[date] = None) -> dict:
    """``{'academic_year', 'semester', 'state'}``; state is in_session, break or holiday."""
    return rules.describe(rules.to_date(on), get_year_windows)