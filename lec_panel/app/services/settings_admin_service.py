"""
Settings Admin Service (Phase 7a)

ONE place defines every admin-editable setting (key, label, help text, type,
range, default). The settings page and every reader use this table, so they
cannot drift apart.

Design notes:

- Readers (``get_setting`` and the two shortcuts below) look the value up AT CALL
  TIME. Nothing is read at import time, so a change applies without a restart.
  Inside a request the value is remembered on ``flask.g`` so a long export does
  not query once per row; saving or resetting clears that memo.

- A reader never raises. A missing row, a blank value or a value outside the
  allowed range all fall back to the default, so the code works before any row
  exists and a bad hand-edit in the database cannot break the attendance pages.

- Defaults are NOT written to the table. A row exists only while an admin has
  chosen a value; "Reset to default" deletes the row.

- ``save`` validates every submitted field first and writes nothing if any field
  is invalid. All changed rows are written in one transaction. Logging happens
  after the commit and never undoes it. One ``SETTINGS_CHANGED`` activity row is
  written per setting that really changed; nothing is logged when nothing changed.

- ``face_recognition_sensitivity`` keeps the key and the 0-100 scale the
  recognition tasks already read (distance = value / 100, default 50), so the
  default behaviour is unchanged.

Academic calendar (Phase 7b): the semester dates are NOT entries of
``SETTING_DEFS`` (that table holds one fixed key per setting). They are one
``settings`` row per academic year, ``academic_calendar_<year>``, handled by the
calendar methods of ``SettingsAdminService`` below. The rules (defaults, overlap
checks, date -> semester) live in ``app/utils/calendar_rules.py`` and the
readers in ``app/utils/academic_calendar.py``; this service only validates,
writes and logs. The same conventions apply: defaults are never stored (saving
the default dates deletes the row), nothing is written if anything is invalid,
one ``SETTINGS_CHANGED`` row is logged after the commit.
"""

import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime

from flask import g, has_app_context
from sqlalchemy import text

from app import db
from app.models.settings import Settings
from app.utils import academic_calendar as calendar
from app.utils import calendar_rules as rules
from config.constants import ActivityType, SettingCategory, UserType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    help: str
    type: str            # 'int' or 'float'
    default: object
    min: object
    max: object
    category: str
    unit: str = ''
    step: str = '1'


SETTING_DEFS = (
    SettingDef(
        key='low_attendance_threshold',
        label='Low attendance threshold',
        help=('A session, class or student is flagged as low attendance when the rate is '
              'under this percentage. Used by the attendance pages and the exports.'),
        type='float', default=75.0, min=1.0, max=100.0, unit='%', step='0.1',
        category=SettingCategory.ATTENDANCE,
    ),
    SettingDef(
        key='lecturer_correction_window_hours',
        label='Lecturer correction window',
        help=('How many hours after a session a lecturer may still correct its attendance. '
              '0 means lecturers cannot correct attendance. Admins are never limited. '
              'Stored now; the lecturer panel starts enforcing it in Phase 8.'),
        type='int', default=48, min=0, max=720, unit='hours', step='1',
        category=SettingCategory.ATTENDANCE,
    ),
    SettingDef(
        key='face_recognition_sensitivity',
        label='Face match sensitivity',
        help=('A face matches a student when its distance is at most this value divided by '
              '100 (50 means 0.50). Lower is stricter: fewer wrong matches but more missed '
              'faces. Higher is more lenient: fewer missed faces but more wrong matches.'),
        type='int', default=50, min=30, max=70, unit='', step='1',
        category=SettingCategory.FACE_RECOGNITION,
    ),
    SettingDef(
        key='final_year_of_study',
        label='Final year of study',
        help=('The last year of study of a programme. At the yearly promotion, active students '
              'already in this year (or beyond) graduate and are deactivated instead of moving '
              'up; everyone else moves up one year. One value for the whole campus.'),
        type='int', default=4, min=1, max=6, unit='', step='1',
        category=SettingCategory.GENERAL,
    ),
)

SETTINGS = {d.key: d for d in SETTING_DEFS}

CATEGORY_ORDER = (SettingCategory.ATTENDANCE, SettingCategory.FACE_RECOGNITION, SettingCategory.GENERAL)
CATEGORY_TITLES = {
    SettingCategory.ATTENDANCE: 'Attendance',
    SettingCategory.FACE_RECOGNITION: 'Face recognition',
    SettingCategory.GENERAL: 'Academic',
}
CATEGORY_NOTES = {
    SettingCategory.FACE_RECOGNITION: (
        'Changing this affects who is recognised in live sessions. '
        'Test it with a few students before relying on it in a real class.'),
}


# ----------------------------------------------------------------------
# Parsing and formatting
# ----------------------------------------------------------------------

def _range_text(d):
    if d.type == 'int':
        return f"{d.min} and {d.max}"
    return f"{d.min:g} and {d.max:g}"


def format_value(d, value):
    """Stored / displayed text of a value (the same text is written to the table)."""
    if d.type == 'int':
        return str(int(value))
    return f"{float(value):.1f}"


def parse_value(d, raw):
    """Return ``(value, None)`` or ``(None, error message)``."""
    raw = '' if raw is None else str(raw).strip()
    if raw == '':
        return None, f"{d.label} is required"
    try:
        if d.type == 'int':
            if not re.fullmatch(r'[+-]?\d+', raw):
                return None, f"{d.label} must be a whole number"
            value = int(raw)
        else:
            value = float(raw)
            if not math.isfinite(value):
                return None, f"{d.label} must be a number"
            value = round(value, 1)
    except ValueError:
        return None, f"{d.label} must be a number"
    if value < d.min or value > d.max:
        return None, f"{d.label} must be between {_range_text(d)}"
    return value, None


def _effective(d, row):
    """The value the system is using: the stored one if valid, else the default."""
    if row is not None and row.setting_value not in (None, ''):
        value, err = parse_value(d, row.setting_value)
        if err is None:
            return value
    return d.default


# ----------------------------------------------------------------------
# Readers (call time, never raise)
# ----------------------------------------------------------------------

def _memo():
    if not has_app_context():
        return None
    memo = getattr(g, '_admin_settings_memo', None)
    if memo is None:
        memo = g._admin_settings_memo = {}
    return memo


def _clear_memo():
    if has_app_context() and hasattr(g, '_admin_settings_memo'):
        g._admin_settings_memo = {}


def get_setting(key):
    """Current value of a defined setting, or its default. Never raises for a bad row."""
    d = SETTINGS[key]          # unknown key = programming error, fail loudly
    memo = _memo()
    if memo is not None and key in memo:
        return memo[key]
    try:
        row = Settings.query.filter_by(setting_key=key).first()
        value = _effective(d, row)
    except Exception as e:
        logger.error(f"Could not read setting {key}: {e}")
        return d.default
    if memo is not None:
        memo[key] = value
    return value


def get_low_threshold():
    """Low-attendance percentage (default 75.0)."""
    return get_setting('low_attendance_threshold')


def get_final_year():
    """Last year of study of a programme (default 4). Used by the yearly promotion (7d)."""
    return get_setting('final_year_of_study')


def get_correction_window_hours():
    """Hours a lecturer may correct attendance after a session (default 48). Enforced in Phase 8."""
    return get_setting('lecturer_correction_window_hours')


# ----------------------------------------------------------------------
# Service used by the settings page
# ----------------------------------------------------------------------

class SettingsAdminService:

    def grouped(self, overrides=None):
        """
        Settings grouped for the page. ``overrides`` (the submitted form after a
        failed save) shows what the admin typed instead of the stored value.
        """
        rows = {}
        try:
            keys = [d.key for d in SETTING_DEFS]
            rows = {r.setting_key: r
                    for r in Settings.query.filter(Settings.setting_key.in_(keys)).all()}
        except Exception as e:
            logger.error(f"Could not list settings: {e}")

        groups = []
        for cat in CATEGORY_ORDER:
            items = []
            for d in SETTING_DEFS:
                if d.category != cat:
                    continue
                row = rows.get(d.key)
                value = _effective(d, row)
                shown = format_value(d, value)
                if overrides is not None and d.key in overrides:
                    shown = str(overrides.get(d.key))
                updated = getattr(row, 'updated_at', None) if row is not None else None
                items.append({
                    'key': d.key, 'label': d.label, 'help': d.help, 'type': d.type,
                    'unit': d.unit, 'min': d.min, 'max': d.max, 'step': d.step,
                    'default_text': format_value(d, d.default),
                    'input_value': shown,
                    'is_default': row is None or value == d.default,
                    'stored': row is not None,
                    'updated_at': updated.strftime('%Y-%m-%d %H:%M') if updated else '',
                })
            groups.append({'category': cat, 'title': CATEGORY_TITLES.get(cat, cat.title()),
                           'note': CATEGORY_NOTES.get(cat, ''), 'items': items})
        return groups

    # ------------------------------------------------------------------

    def save(self, form_values, admin_username):
        """
        Validate every submitted setting, then write the ones that changed in one
        transaction. Returns ``(success, message, errors)``; ``errors`` maps a key
        to its message. A field that was not submitted is left alone.
        """
        errors, new_values = {}, {}
        for d in SETTING_DEFS:
            if d.key not in form_values:
                continue
            value, err = parse_value(d, form_values.get(d.key))
            if err:
                errors[d.key] = err
            else:
                new_values[d.key] = value
        if errors:
            return False, "Nothing was saved. Fix the highlighted fields and try again.", errors

        changes = []
        try:
            rows = {r.setting_key: r for r in Settings.query.filter(
                Settings.setting_key.in_(list(new_values))).all()}
            for d in SETTING_DEFS:
                if d.key not in new_values:
                    continue
                new = new_values[d.key]
                row = rows.get(d.key)
                old = _effective(d, row)
                if new == old:
                    continue
                if row is None:
                    db.session.add(Settings(
                        setting_key=d.key, setting_value=format_value(d, new),
                        description=d.label, category=d.category, is_system=0))
                else:
                    if row.is_system:
                        db.session.rollback()
                        return (False, "Nothing was saved.",
                                {d.key: f"{d.label} is a system setting and cannot be changed here"})
                    row.setting_value = format_value(d, new)
                    row.updated_at = datetime.utcnow()
                changes.append((d, old, new))
            if changes:
                db.session.commit()
        except Exception as e:
            logger.error(f"Settings save error: {e}")
            db.session.rollback()
            return False, "Could not save the settings. Nothing was changed.", {}

        _clear_memo()
        for d, old, new in changes:
            self._log(admin_username,
                      f"Setting '{d.label}' ({d.key}) changed: "
                      f"{format_value(d, old)} -> {format_value(d, new)}")
        if not changes:
            return True, "No changes to save", {}
        n = len(changes)
        return True, f"Saved {n} setting{'' if n == 1 else 's'}", {}

    def reset(self, key, admin_username):
        """Delete the stored row so the built-in default applies. Returns ``(success, message)``."""
        d = SETTINGS.get(key)
        if d is None:
            return False, "Unknown setting"
        try:
            row = Settings.query.filter_by(setting_key=key).first()
            if row is None:
                return True, f"{d.label} is already at its default ({format_value(d, d.default)})"
            if row.is_system:
                return False, f"{d.label} is a system setting and cannot be changed here"
            old = _effective(d, row)
            db.session.delete(row)
            db.session.commit()
        except Exception as e:
            logger.error(f"Settings reset error: {e}")
            db.session.rollback()
            return False, "Could not reset the setting. Nothing was changed."

        _clear_memo()
        if old != d.default:
            self._log(admin_username,
                      f"Setting '{d.label}' ({d.key}) reset to default: "
                      f"{format_value(d, old)} -> {format_value(d, d.default)}")
        return True, f"{d.label} reset to its default ({format_value(d, d.default)})"

    # ------------------------------------------------------------------
    # Academic calendar (Phase 7b)
    # ------------------------------------------------------------------

    def calendar_view(self, year=None, overrides=None):
        """
        Everything the calendar card needs. ``year`` is the academic year being
        edited (default: the current one); ``overrides`` (the submitted form after
        a failed save) shows what the admin typed instead of the stored dates.
        """
        today = date.today()
        current = calendar.get_academic_year(today)
        ay = self._calendar_year(year) or current

        key = rules.year_key(ay)
        row, stored_years = None, set()
        try:
            row = Settings.query.filter_by(setting_key=key).first()
            for r in Settings.query.filter(
                    Settings.setting_key.like(rules.KEY_PREFIX + '%')).all():
                y = rules.year_from_key(r.setting_key)
                if y is not None:
                    stored_years.add(y)
        except Exception as e:
            logger.error(f"Could not read the academic calendar settings: {e}")

        stored = calendar.get_stored_windows(ay) if row is not None else None
        effective = stored or rules.default_windows(ay)
        defaults = rules.default_windows(ay)

        values = self._window_fields(effective)
        if overrides is not None:
            for f in rules.FIELDS:
                if f in overrides:
                    values[f] = str(overrides.get(f))
        default_values = self._window_fields(defaults)

        info = calendar.describe_date(today)
        sem = info['semester']
        where = f"{rules.year_label(info['academic_year'])}"
        if info['state'] == 'in_session':
            today_text = f"Semester {sem} of {where} is in session."
        elif info['state'] == 'break':
            today_text = (f"It is the break between the semesters of {where}; "
                          f"it counts as semester {sem}.")
        else:
            today_text = (f"It is the holiday after the {where} semesters; "
                          f"it counts as semester {sem}.")

        updated = getattr(row, 'updated_at', None) if row is not None else None
        years = sorted({current - 1, current, current + 1, current + 2, ay} | stored_years)
        return {
            'year': ay,
            'label': rules.year_label(ay),
            'is_current': ay == current,
            'options': [{'year': y, 'label': rules.year_label(y),
                         'stored': y in stored_years, 'current': y == current} for y in years],
            'fields': [{'name': f, 'label': rules.FIELD_LABELS[f], 'value': values[f],
                        'default': default_values[f]} for f in rules.FIELDS],
            'stored': row is not None,
            'custom': stored is not None,
            'unusable': row is not None and stored is None,
            'updated_at': updated.strftime('%Y-%m-%d %H:%M') if updated else '',
            'today': today.strftime('%a %d %b %Y'),
            'today_semester': sem,
            'today_text': today_text,
            'today_state': info['state'],
        }

    def save_calendar(self, academic_year, form_values, admin_username):
        """
        Validate the four dates of one academic year (each date, order, overlap
        within the year and with the neighbouring years), then write or delete
        the row in one transaction. Returns ``(success, message, errors)``;
        ``errors`` maps a field name (or ``_calendar``) to its message.
        Saving the default dates deletes the row, because defaults are never stored.
        """
        ay = self._calendar_year(academic_year)
        if ay is None:
            return False, "Choose a valid academic year.", {'_calendar': "Unknown academic year"}

        windows, errors = rules.windows_from_fields(form_values)
        if not errors:
            errors = rules.validate_windows(
                ay, windows,
                previous=calendar.get_year_windows(ay - 1),
                following=calendar.get_year_windows(ay + 1))
        if errors:
            return (False, "Nothing was saved. Fix the highlighted dates and try again.", errors)
        return self._write_calendar(ay, windows, admin_username)

    def reset_calendar(self, academic_year, admin_username):
        """Delete the stored dates of a year so the defaults apply. Returns ``(success, message)``."""
        ay = self._calendar_year(academic_year)
        if ay is None:
            return False, "Unknown academic year"
        defaults = rules.default_windows(ay)
        errors = rules.validate_windows(
            ay, defaults,
            previous=calendar.get_year_windows(ay - 1),
            following=calendar.get_year_windows(ay + 1))
        if errors:
            return (False, f"The default dates for {rules.year_label(ay)} would overlap a "
                           f"neighbouring year: {'; '.join(errors.values())}. "
                           f"Change that year first.")
        ok, message, _ = self._write_calendar(ay, defaults, admin_username)
        return ok, message

    def _write_calendar(self, ay, windows, admin_username):
        key = rules.year_key(ay)
        label = rules.year_label(ay)
        defaults = rules.default_windows(ay)
        semester_before = calendar.get_current_semester()
        change = None                      # (old windows, new windows) when something was written
        try:
            row = Settings.query.filter_by(setting_key=key).first()
            stored = rules.parse_windows(row.setting_value) if row is not None else None
            old = stored if (stored is not None and rules.is_valid_windows(ay, stored)) else defaults

            if row is not None and row.is_system:
                db.session.rollback()
                return (False, "Nothing was saved.",
                        {'_calendar': "This calendar is a system setting and cannot be changed here"})

            if windows == defaults:
                if row is not None:
                    db.session.delete(row)          # defaults are never stored
                    db.session.commit()
                    if old != defaults:
                        change = (old, defaults)
            elif row is None:
                db.session.add(Settings(
                    setting_key=key, setting_value=rules.serialize_windows(windows),
                    description=f"Academic calendar {label}", category=SettingCategory.CALENDAR,
                    is_system=0))
                db.session.commit()
                change = (old, windows)
            elif stored is None or stored != windows:
                row.setting_value = rules.serialize_windows(windows)
                row.updated_at = datetime.utcnow()
                db.session.commit()
                change = (old, windows)
        except Exception as e:
            logger.error(f"Academic calendar save error: {e}")
            db.session.rollback()
            return False, "Could not save the calendar. Nothing was changed.", {}

        calendar.clear_calendar_memo()
        if change is None:
            return True, "No changes to save", {}

        old, new = change
        verb = "reset to the default dates" if new == defaults else "changed"
        self._log(admin_username,
                  f"Academic calendar {label} {verb}: "
                  f"{self._describe_windows(old)} -> {self._describe_windows(new)}")
        message = (f"The {label} calendar is back to the default dates" if new == defaults
                   else f"Saved the {label} calendar")
        semester_after = calendar.get_current_semester()
        if semester_after != semester_before:
            message += (f". The campus semester is now {semester_after} "
                        f"(it was {semester_before}).")
        return True, message, {}

    @staticmethod
    def _calendar_year(value):
        try:
            y = int(value)
        except (TypeError, ValueError):
            return None
        return y if rules.MIN_YEAR <= y <= rules.MAX_YEAR else None

    @staticmethod
    def _window_fields(windows):
        return {'sem1_start': windows[1][0].isoformat(), 'sem1_end': windows[1][1].isoformat(),
                'sem2_start': windows[2][0].isoformat(), 'sem2_end': windows[2][1].isoformat()}

    @staticmethod
    def _describe_windows(w):
        return (f"S1 {w[1][0].isoformat()}..{w[1][1].isoformat()}, "
                f"S2 {w[2][0].isoformat()}..{w[2][1].isoformat()}")

    # ------------------------------------------------------------------

    @staticmethod
    def _log(admin_username, description):
        """Activity log after the commit; a logging problem never undoes the change."""
        try:
            db.session.execute(text("""
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (:user_id, :user_type, :activity_type, :description, :ts)
            """), {'user_id': admin_username, 'user_type': UserType.ADMIN,
                   'activity_type': ActivityType.SETTINGS_CHANGED, 'description': description,
                   'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
            db.session.commit()
        except Exception as e:
            logger.error(f"Settings activity logging error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass