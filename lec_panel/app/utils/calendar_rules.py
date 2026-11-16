"""
Academic calendar rules (Phase 7b)

The ONE place that knows what a semester window is, what the defaults are and
how a date maps to a semester. It uses the standard library only (no Flask, no
database), so the web app and the standalone ``tools/relayout_timetable.py``
both use this same file instead of keeping their own copies.

Storage model (done by ``app/utils/academic_calendar.py`` and the settings
service, not here): one ``settings`` row per academic year, key
``academic_calendar_<year>``, value ``sem1_start,sem1_end,sem2_start,sem2_end``
as ISO dates. A year with no row uses the defaults below.

An academic year is named by the calendar year in which semester 1 starts:
academic year 2026 is 2026/27 (semester 1 in autumn 2026, semester 2 in early
2027, then the holiday).

Every function that needs windows takes ``windows_for``: a callable that
returns the effective windows of an academic year,
``{1: (start, end), 2: (start, end)}`` with ``datetime.date`` values.
"""

from datetime import date, datetime

# (month, day) of each semester's first and last day when nothing is stored.
# Semester 2 falls in the calendar year after the one that names the academic year.
DEFAULT_MONTH_DAYS = {1: ((9, 1), (12, 20)), 2: ((1, 5), (4, 30))}

KEY_PREFIX = 'academic_calendar_'
FIELDS = ('sem1_start', 'sem1_end', 'sem2_start', 'sem2_end')
FIELD_LABELS = {
    'sem1_start': 'Semester 1 start', 'sem1_end': 'Semester 1 end',
    'sem2_start': 'Semester 2 start', 'sem2_end': 'Semester 2 end',
}
MIN_YEAR, MAX_YEAR = 2000, 2100


# ----------------------------------------------------------------------
# Academic year helpers, defaults, storage text
# ----------------------------------------------------------------------

def year_key(academic_year):
    return f"{KEY_PREFIX}{int(academic_year)}"


def year_from_key(key):
    """Academic year of a settings key, or None if it is not a calendar key."""
    if not str(key).startswith(KEY_PREFIX):
        return None
    tail = str(key)[len(KEY_PREFIX):]
    return int(tail) if tail.isdigit() else None


def year_label(academic_year):
    """2026 -> '2026/27'."""
    return f"{int(academic_year)}/{str(int(academic_year) + 1)[2:]}"


def to_date(value):
    """date or datetime -> date (None -> today)."""
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value


def default_windows(academic_year):
    ay = int(academic_year)
    (s1m, s1d), (e1m, e1d) = DEFAULT_MONTH_DAYS[1]
    (s2m, s2d), (e2m, e2d) = DEFAULT_MONTH_DAYS[2]
    return {1: (date(ay, s1m, s1d), date(ay, e1m, e1d)),
            2: (date(ay + 1, s2m, s2d), date(ay + 1, e2m, e2d))}


def serialize_windows(windows):
    return ",".join(d.isoformat() for d in
                    (windows[1][0], windows[1][1], windows[2][0], windows[2][1]))


def parse_windows(text_value):
    """Stored text -> windows, or None when it is missing or malformed."""
    try:
        parts = [p.strip() for p in str(text_value).split(',')]
        if len(parts) != 4:
            return None
        d = [datetime.strptime(p, '%Y-%m-%d').date() for p in parts]
    except (TypeError, ValueError):
        return None
    return {1: (d[0], d[1]), 2: (d[2], d[3])}


def windows_from_fields(values):
    """
    ``{field: 'YYYY-MM-DD'}`` -> ``(windows, errors)``. ``errors`` maps a field
    name to a message; ``windows`` is None when any field is bad.
    """
    errors, parsed = {}, {}
    for f in FIELDS:
        raw = str(values.get(f) or '').strip()
        if not raw:
            errors[f] = f"{FIELD_LABELS[f]} is required"
            continue
        try:
            parsed[f] = datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            errors[f] = f"{FIELD_LABELS[f]} must be a valid date"
    if errors:
        return None, errors
    return ({1: (parsed['sem1_start'], parsed['sem1_end']),
             2: (parsed['sem2_start'], parsed['sem2_end'])}, {})


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

def validate_windows(academic_year, windows, previous=None, following=None):
    """
    Check one academic year's windows. Returns a dict ``{field or '_calendar':
    message}``; empty means valid. ``previous`` / ``following`` are the effective
    windows of the neighbouring academic years (so two years can't overlap).
    """
    ay = int(academic_year)
    errors = {}
    (s1, e1), (s2, e2) = windows[1], windows[2]

    if e1 <= s1:
        errors['sem1_end'] = "Semester 1 must end after it starts"
    if e2 <= s2:
        errors['sem2_end'] = "Semester 2 must end after it starts"
    if s2 <= e1:
        errors['sem2_start'] = ("Semester 2 must start after semester 1 ends "
                                "(the two semesters overlap)")
    if s1.year != ay:
        errors['sem1_start'] = (f"Semester 1 of {year_label(ay)} must start in {ay} "
                                f"(an academic year is named after the year semester 1 starts)")
    if 'sem2_end' not in errors and (e2 - s1).days > 366:
        errors['sem2_end'] = "Both semesters must fit within one year"

    if previous is not None and 'sem1_start' not in errors and previous[2][1] >= s1:
        errors['sem1_start'] = (f"Semester 1 starts before the {year_label(ay - 1)} calendar "
                                f"ends ({previous[2][1].isoformat()})")
    if following is not None and 'sem2_end' not in errors and e2 >= following[1][0]:
        errors['sem2_end'] = (f"Semester 2 ends after the {year_label(ay + 1)} calendar "
                              f"starts ({following[1][0].isoformat()})")
    return errors


def is_valid_windows(academic_year, windows):
    return not validate_windows(academic_year, windows)


# ----------------------------------------------------------------------
# Date -> semester
# ----------------------------------------------------------------------

def academic_year_of(on, windows_for):
    """The academic year a date belongs to: the latest one whose semester 1 has started."""
    on = to_date(on)
    for ay in (on.year, on.year - 1):
        if windows_for(ay)[1][0] <= on:
            return ay
    return on.year - 1


def semester_on(on, windows_for):
    """
    Campus semester (1 or 2) of a date.

    Inside a window it is that semester. The days between the two windows count
    as semester 1 until 31 December and as semester 2 from 1 January (if the gap
    has no 1 January in it, it belongs to the semester that just ended). The
    holiday after semester 2 counts as semester 2.
    """
    on = to_date(on)
    w = _windows(on, windows_for)
    (s1, e1), (s2, e2) = w[1], w[2]
    if on <= e1:
        return 1
    if on < s2:
        return 2 if on.year > e1.year else 1
    return 2


def in_semester_on(on, windows_for):
    """True only inside a semester window (breaks and the holiday are False)."""
    on = to_date(on)
    w = _windows(on, windows_for)
    (s1, e1), (s2, e2) = w[1], w[2]
    return s1 <= on <= e1 or s2 <= on <= e2


def describe(on, windows_for):
    """
    What a date is: ``{'academic_year', 'semester', 'state'}`` with state
    ``'in_session'``, ``'break'`` (between the semesters) or ``'holiday'``.
    """
    on = to_date(on)
    ay = academic_year_of(on, windows_for)
    w = windows_for(ay)
    if w[1][0] <= on <= w[1][1] or w[2][0] <= on <= w[2][1]:
        state = 'in_session'
    elif w[1][1] < on < w[2][0]:
        state = 'break'
    else:
        state = 'holiday'
    return {'academic_year': ay, 'semester': semester_on(on, windows_for), 'state': state}


def semester_window(semester, today, windows_for):
    """
    The ``(start, end)`` of the window of ``semester`` that contains ``today`` or
    is the next one to begin (the first whose end is not before today).
    """
    today = to_date(today)
    sem = 2 if int(semester) == 2 else 1
    last = None
    for ay in (today.year - 1, today.year, today.year + 1):
        last = windows_for(ay)[sem]
        if last[1] >= today:
            return last
    return last


def _windows(on, windows_for):
    return windows_for(academic_year_of(on, windows_for))