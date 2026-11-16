"""
Timetable Admin Service
Admin-side ownership of the campus-wide master timetable: entry CRUD with
conflict detection, holiday management, and bulk session generation.

Design notes (match the live data, not the ORM):

- Everything here uses plain ``text()`` SQL. The live database stores session
  dates/times as text ('2026-11-09', '15:00') and dates as ISO strings, while
  the ORM declares Date/Time columns, and two different ``Holiday`` classes map
  to the one ``holidays`` table. SessionService already reads sessions with raw
  SQL for the same reasons; this service writes them the same way, in exactly
  the format the existing rows use.

- The timetable is a *recurring weekly template*: it is created once and then
  tweaked during the first weeks of a semester. So edits flow through to
  sessions that were already generated: when a slot changes, future sessions
  of the old slot that nobody has touched are removed and regenerated from the
  new slot (see ``_purge_untouched``). A session counts as untouched when it is
  still 'scheduled' and has no attendance, dismissal or metric rows.

- Generation never back-fills the past, never modifies an existing session,
  and treats ANY existing session at the same class/date/start time as a
  duplicate, so a session a lecturer cancelled is not resurrected.

- Conflicts (hard blocks) are checked only between entries of the same campus
  semester whose effective-date ranges overlap:
    * class    - the same class at overlapping times
    * lecturer - a lecturer assigned to both classes (via class_instructors)
    * cohort   - same course + year (students attend every class)
  There is no room column, so rooms are not checked.

- Semester windows below are a stand-in until Phase 7 (academic-calendar
  settings). They only pre-fill form defaults; the admin can always edit dates.

Methods that change data return (success, message[, extra]) tuples, like the
other admin services.
"""

from datetime import date, datetime, timedelta
import logging

from sqlalchemy import bindparam, text

from app import db
from app.utils.academic_calendar import (
    get_current_semester,
    semester_window as _calendar_semester_window,
)
from config.constants import ActivityType, DayOfWeek, UserType

logger = logging.getLogger(__name__)

# Monday first, Sunday last (schema stores 0 = Sunday)
DAY_ORDER = (1, 2, 3, 4, 5, 6, 0)
DAY_NAMES = DayOfWeek.NAMES
WEEKDAYS = (1, 2, 3, 4, 5)

MAX_GENERATION_DAYS = 200

# A session nobody has touched: still scheduled, nothing hangs off it.
_UNTOUCHED_SQL = """
    s.status = 'scheduled'
    AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.session_id = s.session_id)
    AND NOT EXISTS (SELECT 1 FROM session_dismissals d WHERE d.session_id = s.session_id)
    AND NOT EXISTS (SELECT 1 FROM system_metrics m WHERE m.session_id = s.session_id)
"""

_OPEN_STATES = ('cancelled', 'dismissed')


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def _today():
    return date.today()


def _now_hm():
    return datetime.now().strftime('%H:%M')


def _to_date(value):
    """Accept date, datetime, 'YYYY-MM-DD...' or empty. Empty -> None."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d').date()


def _norm_time(value):
    """Return a zero-padded 'HH:MM' string or raise ValueError."""
    return datetime.strptime(str(value).strip()[:5], '%H:%M').strftime('%H:%M')


def _minutes(hhmm):
    hours, minutes = str(hhmm)[:5].split(':')
    return int(hours) * 60 + int(minutes)


def _times_overlap(start1, end1, start2, end2):
    return _minutes(start1) < _minutes(end2) and _minutes(start2) < _minutes(end1)


def _dates_overlap(from1, to1, from2, to2):
    """Date ranges overlap; a None end means open-ended."""
    if to1 is not None and from2 is not None and from2 > to1:
        return False
    if to2 is not None and from1 is not None and from1 > to2:
        return False
    return True


def _sem_int(value):
    try:
        return int(str(value).strip().split('.')[-1])
    except (TypeError, ValueError):
        return None


def semester_window(semester, today=None):
    """
    The (start, end) dates of the semester window that contains `today` or is
    the next one to begin. The dates come from the academic calendar the admin
    maintains on /admin/settings (app/utils/academic_calendar.py).
    """
    return _calendar_semester_window(_sem_int(semester) or 1, today or _today())


def group_by_day(entries):
    """
    Arrange entries for the weekly grid.

    Returns (days_shown, grid): Monday-Friday always, Saturday/Sunday only when
    they have entries; grid maps day -> entries sorted by start time.
    """
    grid = {d: [] for d in DAY_ORDER}
    for entry in entries:
        grid[entry['day_of_week']].append(entry)
    for items in grid.values():
        items.sort(key=lambda e: (e['start_time'], e['class_id']))
    days_shown = [d for d in DAY_ORDER if d in WEEKDAYS or grid[d]]
    return days_shown, grid


class TimetableAdminService:
    """Admin management of the campus timetable, holidays and session generation."""

    # ==================================================================
    # Reference data
    # ==================================================================

    def get_filter_options(self):
        """Active courses and lecturers for filter dropdowns."""
        courses = db.session.execute(text(
            "SELECT course_code, course_name FROM courses "
            "WHERE is_active = 1 ORDER BY course_code"
        )).mappings().all()
        instructors = db.session.execute(text(
            "SELECT instructor_id, instructor_name FROM instructors "
            "WHERE is_active = 1 ORDER BY instructor_name"
        )).mappings().all()
        return [dict(r) for r in courses], [dict(r) for r in instructors]

    def get_selectable_classes(self):
        """Active classes (with lecturer names) for the entry form."""
        rows = db.session.execute(text(
            "SELECT class_id, class_name, course_code, year, semester "
            "FROM classes WHERE is_active = 1 ORDER BY course_code, year, class_id"
        )).mappings().all()
        lecturers = self._lecturers_by_class()

        classes = []
        for row in rows:
            item = dict(row)
            item['semester'] = _sem_int(item['semester'])
            item['lecturers'] = [
                l['instructor_name'] for l in lecturers.get(item['class_id'], [])
            ]
            classes.append(item)
        return classes

    def window_defaults(self):
        """ISO (from, to) form defaults per semester, e.g. {1: [...], 2: [...]}."""
        today = _today()
        defaults = {}
        for sem in (1, 2):
            start, end = semester_window(sem, today)
            defaults[sem] = [start.isoformat(), end.isoformat()]
        return defaults

    # ==================================================================
    # Entries: reading
    # ==================================================================

    def list_entries(self, semester=None, course_code=None, year=None,
                     instructor_id=None, day=None, class_id=None, status='active'):
        """Timetable entries (dicts) matching the filters, Monday-first."""
        where, params = [], {}

        if semester:
            where.append("c.semester = :semester")
            params['semester'] = int(semester)
        if course_code:
            where.append("c.course_code = :course")
            params['course'] = course_code
        if year:
            where.append("c.year = :year")
            params['year'] = int(year)
        if instructor_id:
            where.append(
                "EXISTS (SELECT 1 FROM class_instructors ci "
                "WHERE ci.class_id = t.class_id AND ci.instructor_id = :iid)"
            )
            params['iid'] = instructor_id
        if day is not None:
            where.append("t.day_of_week = :day")
            params['day'] = int(day)
        if class_id:
            where.append("t.class_id LIKE :cid")
            params['cid'] = f"%{class_id.strip()}%"
        if status == 'active':
            where.append("t.is_active = 1")
        elif status == 'inactive':
            where.append("t.is_active = 0")

        return self._load_entries(" AND ".join(where), params)

    def get_entry(self, entry_id):
        rows = self._load_entries("t.id = :id", {'id': entry_id})
        return rows[0] if rows else None

    # ==================================================================
    # Entries: writing
    # ==================================================================

    def create_entry(self, admin_username, class_id, day_of_week, start_time, end_time,
                     effective_from, effective_to, generate_now=False):
        """
        Add a recurring slot. Blocks on class/lecturer/cohort clashes.

        With generate_now, also creates the sessions for this class from today
        (or the effective start) to the effective end.

        Returns (success, message, entry_id).
        """
        error, clean = self._clean_slot(
            class_id, day_of_week, start_time, end_time,
            effective_from, effective_to, require_class_active=True
        )
        if error:
            return False, error, None

        conflicts = self.find_conflicts(
            clean['class_id'], clean['day'], clean['start'], clean['end'],
            clean['from'], clean['to']
        )
        if conflicts:
            return False, self.format_conflicts(conflicts), None

        try:
            result = db.session.execute(text("""
                INSERT INTO timetable
                    (class_id, day_of_week, start_time, end_time, is_active,
                     effective_from, effective_to)
                VALUES (:class_id, :day, :start, :end, 1, :efrom, :eto)
            """), {
                'class_id': clean['class_id'], 'day': clean['day'],
                'start': clean['start'], 'end': clean['end'],
                'efrom': clean['from'].isoformat(),
                'eto': clean['to'].isoformat() if clean['to'] else None,
            })
            entry_id = result.lastrowid

            message = (f"Timetable entry added: {clean['class_id']}, "
                       f"{DAY_NAMES[clean['day']]} {clean['start']}-{clean['end']}.")
            generated = 0

            if generate_now and clean['to']:
                start = max(_today(), clean['from'])
                if clean['to'] >= start:
                    plan = self.plan_generation(
                        start, clean['to'], class_id=clean['class_id']
                    )
                    if plan['ok']:
                        self._execute_plan(plan)
                        generated = plan['total']
                        message += f" {generated} session(s) generated."

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Timetable entry create error: {str(e)}")
            return False, "Failed to create timetable entry", None

        self._log_admin_activity(
            admin_username, ActivityType.PROFILE_UPDATED,
            f"Added timetable entry {entry_id}: {clean['class_id']} "
            f"{DAY_NAMES[clean['day']]} {clean['start']}-{clean['end']} "
            f"({clean['from']} to {clean['to'] or 'open'}); {generated} session(s) generated"
        )
        return True, message, entry_id

    def update_entry(self, admin_username, entry_id, day_of_week, start_time, end_time,
                     effective_from, effective_to, propagate=True):
        """
        Edit a slot (the class itself can't change). Blocks on clashes.

        With propagate, future untouched sessions of the OLD slot are removed
        and regenerated from the new slot, up to the furthest date that had
        been generated. Everything happens in one transaction.

        Returns (success, message).
        """
        old = self.get_entry(entry_id)
        if not old:
            return False, "Timetable entry not found"

        error, clean = self._clean_slot(
            old['class_id'], day_of_week, start_time, end_time,
            effective_from, effective_to, require_class_active=False
        )
        if error:
            return False, error

        if old['is_active']:
            conflicts = self.find_conflicts(
                old['class_id'], clean['day'], clean['start'], clean['end'],
                clean['from'], clean['to'], exclude_id=entry_id
            )
            if conflicts:
                return False, self.format_conflicts(conflicts)

        slot_changed = (
            old['day_of_week'] != clean['day']
            or old['start_time'] != clean['start']
            or old['end_time'] != clean['end']
            or old['effective_from'] != clean['from']
            or old['effective_to'] != clean['to']
        )

        purged = regenerated = 0
        try:
            db.session.execute(text("""
                UPDATE timetable
                SET day_of_week = :day, start_time = :start, end_time = :end,
                    effective_from = :efrom, effective_to = :eto
                WHERE id = :id
            """), {
                'day': clean['day'], 'start': clean['start'], 'end': clean['end'],
                'efrom': clean['from'].isoformat(),
                'eto': clean['to'].isoformat() if clean['to'] else None,
                'id': entry_id,
            })

            if propagate and slot_changed:
                purged, removed_dates = self._purge_slot_sessions(
                    old['class_id'], old['day_of_week'],
                    old['start_time'], old['end_time']
                )
                if purged and old['is_active']:
                    regenerated = self._recreate_in_same_weeks(
                        old['class_id'], removed_dates,
                        clean['day'], clean['start'], clean['end']
                    )

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Timetable entry update error: {str(e)}")
            return False, "Failed to update timetable entry"

        self._log_admin_activity(
            admin_username, ActivityType.PROFILE_UPDATED,
            f"Updated timetable entry {entry_id} ({old['class_id']}): "
            f"{old['day_name']} {old['start_time']}-{old['end_time']} -> "
            f"{DAY_NAMES[clean['day']]} {clean['start']}-{clean['end']}; "
            f"{purged} session(s) removed, {regenerated} recreated"
        )

        message = f"Timetable entry for {old['class_id']} updated."
        if propagate and slot_changed:
            message += (f" {purged} upcoming session(s) removed, "
                        f"{regenerated} recreated on the new slot.")
            if purged > regenerated:
                message += (f" {purged - regenerated} could not be recreated "
                            "(holiday, clash, or outside the entry's dates).")
        elif slot_changed:
            message += " Existing sessions were left as they are."
        return True, message

    def deactivate_entry(self, admin_username, entry_id, propagate=True):
        """Switch a slot off. Optionally removes its future untouched sessions."""
        entry = self.get_entry(entry_id)
        if not entry:
            return False, "Timetable entry not found"
        if not entry['is_active']:
            return False, "Entry is already inactive"

        purged = 0
        try:
            db.session.execute(
                text("UPDATE timetable SET is_active = 0 WHERE id = :id"), {'id': entry_id}
            )
            if propagate:
                purged, _ = self._purge_slot_sessions(
                    entry['class_id'], entry['day_of_week'],
                    entry['start_time'], entry['end_time']
                )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Timetable entry deactivate error: {str(e)}")
            return False, "Failed to deactivate timetable entry"

        self._log_admin_activity(
            admin_username, ActivityType.ACCOUNT_DEACTIVATED,
            f"Deactivated timetable entry {entry_id} ({entry['class_id']} "
            f"{entry['day_name']} {entry['start_time']}); {purged} session(s) removed"
        )
        message = f"Entry for {entry['class_id']} deactivated."
        if propagate:
            message += f" {purged} upcoming session(s) removed."
        return True, message

    def activate_entry(self, admin_username, entry_id):
        """Switch a slot back on, after re-checking clashes."""
        entry = self.get_entry(entry_id)
        if not entry:
            return False, "Timetable entry not found"
        if entry['is_active']:
            return False, "Entry is already active"

        conflicts = self.find_conflicts(
            entry['class_id'], entry['day_of_week'], entry['start_time'],
            entry['end_time'], entry['effective_from'], entry['effective_to'],
            exclude_id=entry_id
        )
        if conflicts:
            return False, self.format_conflicts(conflicts)

        try:
            db.session.execute(
                text("UPDATE timetable SET is_active = 1 WHERE id = :id"), {'id': entry_id}
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Timetable entry activate error: {str(e)}")
            return False, "Failed to activate timetable entry"

        self._log_admin_activity(
            admin_username, ActivityType.ACCOUNT_ACTIVATED,
            f"Activated timetable entry {entry_id} ({entry['class_id']} "
            f"{entry['day_name']} {entry['start_time']})"
        )
        return True, (f"Entry for {entry['class_id']} activated. "
                      "Run Generate sessions to create its sessions.")

    def delete_entry(self, admin_username, entry_id, propagate=True):
        """
        Permanently delete a slot. Nothing references timetable rows, so this
        is always safe; sessions already held are never touched.
        """
        entry = self.get_entry(entry_id)
        if not entry:
            return False, "Timetable entry not found"

        purged = 0
        try:
            if propagate:
                purged, _ = self._purge_slot_sessions(
                    entry['class_id'], entry['day_of_week'],
                    entry['start_time'], entry['end_time']
                )
            db.session.execute(
                text("DELETE FROM timetable WHERE id = :id"), {'id': entry_id}
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Timetable entry delete error: {str(e)}")
            return False, "Failed to delete timetable entry"

        self._log_admin_activity(
            admin_username, ActivityType.PROFILE_UPDATED,
            f"Deleted timetable entry {entry_id} ({entry['class_id']} "
            f"{entry['day_name']} {entry['start_time']}); {purged} session(s) removed"
        )
        message = f"Entry for {entry['class_id']} deleted."
        if propagate:
            message += f" {purged} upcoming session(s) removed."
        return True, message

    # ==================================================================
    # Conflicts
    # ==================================================================

    def find_conflicts(self, class_id, day_of_week, start_time, end_time,
                       effective_from, effective_to, exclude_id=None):
        """
        Clashes a slot would cause. Returns a list of dicts
        {'kind': 'class'|'lecturer'|'cohort', 'entry': <entry>, 'message': str}.
        """
        cls = self._get_class_row(class_id)
        if not cls:
            return []

        others = self._load_entries(
            "t.is_active = 1 AND c.is_active = 1 "
            "AND t.day_of_week = :dow AND c.semester = :sem",
            {'dow': int(day_of_week), 'sem': cls['semester']}
        )
        mine = {
            l['instructor_id']
            for l in self._lecturers_by_class().get(class_id, [])
        }

        conflicts = []
        for e in others:
            if exclude_id and e['id'] == exclude_id:
                continue
            if not _times_overlap(start_time, end_time, e['start_time'], e['end_time']):
                continue
            if not _dates_overlap(effective_from, effective_to,
                                  e['effective_from'], e['effective_to']):
                continue

            slot = f"{e['day_name']} {e['start_time']}-{e['end_time']}"

            if e['class_id'] == class_id:
                conflicts.append({
                    'kind': 'class', 'entry': e,
                    'message': f"{class_id} already has a slot on {slot}",
                })
                continue

            shared = mine & e['lecturer_ids']
            if shared:
                names = ', '.join(
                    l['instructor_name'] for l in e['lecturers']
                    if l['instructor_id'] in shared
                )
                conflicts.append({
                    'kind': 'lecturer', 'entry': e,
                    'message': f"{names} already teaches {e['class_id']} on {slot}",
                })

            if (e['course_code'], e['year']) == (cls['course_code'], cls['year']):
                conflicts.append({
                    'kind': 'cohort', 'entry': e,
                    'message': (f"{e['class_id']} is in the same cohort "
                                f"({cls['course_code']} year {cls['year']}) on {slot}"),
                })
        return conflicts

    def check_slot(self, class_id, day_of_week, start_time, end_time,
                   effective_from, effective_to, exclude_id=None):
        """
        Clashes for a possibly half-filled form (live check). Returns [] while
        the input is incomplete or invalid, so the form can call it freely.
        """
        try:
            start, end = _norm_time(start_time), _norm_time(end_time)
            eff_from, eff_to = _to_date(effective_from), _to_date(effective_to)
            day = int(day_of_week)
        except (TypeError, ValueError):
            return []
        if (not class_id or eff_from is None or not 0 <= day <= 6
                or _minutes(end) <= _minutes(start)):
            return []
        return self.find_conflicts(
            class_id, day, start, end, eff_from, eff_to, exclude_id=exclude_id
        )

    @staticmethod
    def format_conflicts(conflicts, limit=3):
        """One readable sentence for a flash message."""
        shown = '; '.join(c['message'] for c in conflicts[:limit])
        extra = len(conflicts) - limit
        if extra > 0:
            shown += f"; and {extra} more"
        return f"Clash: {shown}."

    def check_lecturer_assignment(self, instructor_id, class_id):
        """
        Clashes that assigning this lecturer to this class would create with
        the lecturer's existing classes. Returns a list of readable strings.
        """
        cls = self._get_class_row(class_id)
        if not cls:
            return []

        mine = self._load_entries(
            "t.is_active = 1 AND t.class_id = :cid", {'cid': class_id}
        )
        if not mine:
            return []

        theirs = self._load_entries(
            "t.is_active = 1 AND c.is_active = 1 AND c.semester = :sem "
            "AND t.class_id <> :cid AND EXISTS (SELECT 1 FROM class_instructors ci "
            "WHERE ci.class_id = t.class_id AND ci.instructor_id = :iid)",
            {'sem': cls['semester'], 'cid': class_id, 'iid': instructor_id}
        )

        clashes = []
        for a in mine:
            for b in theirs:
                if (a['day_of_week'] == b['day_of_week']
                        and _times_overlap(a['start_time'], a['end_time'],
                                           b['start_time'], b['end_time'])
                        and _dates_overlap(a['effective_from'], a['effective_to'],
                                           b['effective_from'], b['effective_to'])):
                    clashes.append(
                        f"{b['class_id']} {b['day_name']} {b['start_time']}-{b['end_time']} "
                        f"overlaps {a['class_id']} {a['day_name']} "
                        f"{a['start_time']}-{a['end_time']}"
                    )
        return clashes

    def audit(self, semester):
        """
        Scan the whole active timetable of a semester for clashes, plus classes
        that have no timetable entry or no active lecturer.
        """
        entries = self._load_entries(
            "t.is_active = 1 AND c.is_active = 1 AND c.semester = :sem",
            {'sem': int(semester)}
        )

        issues = self._find_issues(entries)

        no_timetable = db.session.execute(text("""
            SELECT c.class_id, c.class_name, c.course_code, c.year
            FROM classes c
            WHERE c.is_active = 1 AND c.semester = :sem
              AND NOT EXISTS (SELECT 1 FROM timetable t
                              WHERE t.class_id = c.class_id AND t.is_active = 1)
            ORDER BY c.course_code, c.year, c.class_id
        """), {'sem': int(semester)}).mappings().all()

        no_lecturer = db.session.execute(text("""
            SELECT c.class_id, c.class_name, c.course_code, c.year
            FROM classes c
            WHERE c.is_active = 1 AND c.semester = :sem
              AND NOT EXISTS (SELECT 1 FROM class_instructors ci
                              JOIN instructors i ON i.instructor_id = ci.instructor_id
                              WHERE ci.class_id = c.class_id AND i.is_active = 1)
            ORDER BY c.course_code, c.year, c.class_id
        """), {'sem': int(semester)}).mappings().all()

        counts = {'class': 0, 'lecturer': 0, 'cohort': 0}
        for issue in issues:
            counts[issue['kind']] += 1

        return {
            'issues': issues,
            'counts': counts,
            'entry_count': len(entries),
            'no_timetable': [dict(r) for r in no_timetable],
            'no_lecturer': [dict(r) for r in no_lecturer],
        }

    def cohort_summary(self, semester=None, course_code=None, year=None):
        """
        One summary per cohort (course + year + semester) for the overview.

        Clashes are detected across the WHOLE active timetable of the semester,
        so a lecturer clash with another cohort still counts against this one.
        Returns a list of dicts sorted by course, year, semester.
        """
        where, params = ["c.is_active = 1"], {}
        if semester:
            where.append("c.semester = :sem")
            params['sem'] = int(semester)

        classes = db.session.execute(text(
            "SELECT c.class_id, c.course_code, co.course_name, c.year, c.semester "
            "FROM classes c LEFT JOIN courses co ON co.course_code = c.course_code "
            "WHERE " + " AND ".join(where)
        ), params).mappings().all()

        entries = self._load_entries(
            "t.is_active = 1 AND c.is_active = 1"
            + (" AND c.semester = :sem" if semester else ""), params
        )
        issues = self._find_issues(entries)
        today = _today()

        def key_of(item):
            return (item['course_code'], item['year'], _sem_int(item['semester']))

        cohorts, scheduled = {}, {}
        for row in classes:
            key = key_of(row)
            if course_code and key[0] != course_code:
                continue
            if year and key[1] != int(year):
                continue
            cohort = cohorts.setdefault(key, {
                'course_code': key[0], 'course_name': row['course_name'] or key[0],
                'year': key[1], 'semester': key[2], 'class_count': 0,
                'entry_count': 0, 'expired': 0, 'clashes': 0, 'unscheduled': 0,
            })
            cohort['class_count'] += 1
            scheduled.setdefault(key, set())

        for e in entries:
            key = key_of(e)
            if key not in cohorts:
                continue
            cohorts[key]['entry_count'] += 1
            scheduled[key].add(e['class_id'])
            if e['effective_to'] and e['effective_to'] < today:
                cohorts[key]['expired'] += 1

        for issue in issues:
            for key in {key_of(issue['a']), key_of(issue['b'])}:
                if key in cohorts:
                    cohorts[key]['clashes'] += 1

        for key, cohort in cohorts.items():
            cohort['unscheduled'] = cohort['class_count'] - len(scheduled[key])

        return sorted(cohorts.values(),
                      key=lambda c: (c['course_code'], c['year'], c['semester'] or 0))

    def classes_without_slot(self, semester=None, course_code=None, year=None,
                             instructor_id=None):
        """Active classes in scope that have no active timetable entry."""
        where = ["c.is_active = 1",
                 "NOT EXISTS (SELECT 1 FROM timetable t "
                 "WHERE t.class_id = c.class_id AND t.is_active = 1)"]
        params = {}
        if semester:
            where.append("c.semester = :sem")
            params['sem'] = int(semester)
        if course_code:
            where.append("c.course_code = :course")
            params['course'] = course_code
        if year:
            where.append("c.year = :year")
            params['year'] = int(year)
        if instructor_id:
            where.append("EXISTS (SELECT 1 FROM class_instructors ci "
                         "WHERE ci.class_id = c.class_id AND ci.instructor_id = :iid)")
            params['iid'] = instructor_id

        rows = db.session.execute(text(
            "SELECT c.class_id, c.class_name, c.course_code, c.year, c.semester "
            "FROM classes c WHERE " + " AND ".join(where) +
            " ORDER BY c.course_code, c.year, c.class_id"
        ), params).mappings().all()
        return [dict(r) for r in rows]

    def week_layout(self, entries, semester=None):
        """
        Lay entries out as a time-of-day calendar.

        Overlapping blocks are placed side by side in lanes. A block is flagged
        when it is part of a real clash (class / lecturer / cohort); clashes are
        looked for across the whole active timetable, not just `entries`, so a
        filtered view still shows clashes with classes that are filtered out.

        Returns {'empty', 'hours', 'hour_px', 'height_px', 'days': [...]} where
        each day holds items with CSS percentages (top/height/left/width).
        """
        hour_px = 56
        layout = {'empty': not entries, 'hours': [], 'hour_px': hour_px,
                  'height_px': 0, 'days': []}
        if not entries:
            return layout

        context = self._load_entries(
            "t.is_active = 1 AND c.is_active = 1"
            + (" AND c.semester = :sem" if semester else ""),
            {'sem': int(semester)} if semester else {}
        )
        labels = {'lecturer': 'Lecturer clash', 'cohort': 'Cohort clash',
                  'class': 'Same class twice'}
        flags = {}
        for issue in self._find_issues(context):
            a, b, label = issue['a'], issue['b'], labels[issue['kind']]
            flags.setdefault(a['id'], []).append(
                f"{label} with {b['class_id']} ({b['start_time']}-{b['end_time']})")
            flags.setdefault(b['id'], []).append(
                f"{label} with {a['class_id']} ({a['start_time']}-{a['end_time']})")

        # Visible hours wrap the data tightly (so there is nothing to scroll past),
        # but never less than six hours so a single block doesn't look stretched
        start_min = max(0, min(_minutes(e['start_time']) for e in entries) // 60 * 60)
        end_min = min(24 * 60, -(-max(_minutes(e['end_time']) for e in entries) // 60) * 60)
        if end_min - start_min < 6 * 60:
            end_min = min(24 * 60, start_min + 6 * 60)
            start_min = max(0, end_min - 6 * 60)
        span = end_min - start_min
        today = _today()

        layout['hours'] = list(range(start_min // 60, end_min // 60))
        layout['height_px'] = len(layout['hours']) * hour_px

        days_shown, grid = group_by_day(entries)
        for day in days_shown:
            items, cluster, cluster_end = [], [], -1

            def close_cluster():
                lanes = max(it['lane'] for it in cluster) + 1
                for it in cluster:
                    it['left'] = round(it['lane'] / lanes * 100, 3)
                    it['width'] = round(100 / lanes, 3)

            for e in sorted(grid[day], key=lambda e: (
                    _minutes(e['start_time']), _minutes(e['end_time']), e['class_id'])):
                s_min, e_min = _minutes(e['start_time']), _minutes(e['end_time'])
                if cluster and s_min >= cluster_end:
                    close_cluster()
                    cluster, cluster_end = [], -1
                lane = 0
                taken = {it['lane'] for it in cluster if it['end'] > s_min}
                while lane in taken:
                    lane += 1
                item = {
                    'entry': e, 'lane': lane, 'end': e_min,
                    'top': round((s_min - start_min) / span * 100, 3),
                    'height': round((e_min - s_min) / span * 100, 3),
                    'compact': (e_min - s_min) < 75,
                    'clashes': flags.get(e['id'], []),
                    'dim': (not e['is_active'])
                           or bool(e['effective_to'] and e['effective_to'] < today),
                }
                cluster.append(item)
                items.append(item)
                cluster_end = max(cluster_end, e_min)
            if cluster:
                close_cluster()

            layout['days'].append({'day': day, 'name': DAY_NAMES[day], 'blocks': items})
        return layout

    # ==================================================================
    # Holidays
    # ==================================================================

    def list_holidays(self, year=None):
        """Holidays (dicts) for a year, or all of them when year is None."""
        sql = "SELECT id, name, date, description, is_recurring FROM holidays"
        params = {}
        if year:
            sql += " WHERE date >= :start AND date <= :end"
            params = {'start': f"{int(year):04d}-01-01", 'end': f"{int(year):04d}-12-31"}
        sql += " ORDER BY date, name"

        holidays = []
        for row in db.session.execute(text(sql), params).mappings().all():
            item = dict(row)
            item['date'] = _to_date(item['date'])
            item['is_recurring'] = bool(item['is_recurring'])
            holidays.append(item)
        return holidays

    def holiday_years(self):
        """Years that have holidays, plus last/this/next year, newest first."""
        rows = db.session.execute(text(
            "SELECT DISTINCT substr(date, 1, 4) AS y FROM holidays"
        )).fetchall()
        years = {int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()}
        this_year = _today().year
        years.update({this_year - 1, this_year, this_year + 1})
        return sorted(years, reverse=True)

    def create_holiday(self, admin_username, name, holiday_date, description=None,
                       is_recurring=False, remove_sessions=True):
        """Add a holiday. Optionally removes untouched scheduled sessions that day."""
        name = (name or '').strip()
        if not name:
            return False, "Holiday name is required"
        if len(name) > 200:
            return False, "Holiday name is too long (max 200 characters)"
        try:
            hdate = _to_date(holiday_date)
        except ValueError:
            return False, "Enter a valid date"
        if hdate is None:
            return False, "Date is required"

        if self._holiday_exists(hdate, name):
            return False, f"{name} is already recorded for {hdate.isoformat()}"

        removed = 0
        try:
            db.session.execute(text("""
                INSERT INTO holidays (name, date, description, is_recurring, created_at)
                VALUES (:name, :date, :description, :recurring, :created)
            """), {
                'name': name, 'date': hdate.isoformat(),
                'description': (description or '').strip() or None,
                'recurring': 1 if is_recurring else 0,
                'created': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            })
            if remove_sessions:
                removed, _ = self._purge_untouched("s.date = :d", {'d': hdate.isoformat()})
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Holiday create error: {str(e)}")
            return False, "Failed to add holiday"

        self._log_admin_activity(
            admin_username, ActivityType.SETTINGS_CHANGED,
            f"Added holiday '{name}' on {hdate.isoformat()}; {removed} session(s) removed"
        )
        message = f"{name} added for {hdate.strftime('%d %b %Y')}."
        if remove_sessions:
            message += f" {removed} untouched scheduled session(s) removed."
        return True, message

    def update_holiday(self, admin_username, holiday_id, name, holiday_date,
                       description=None, is_recurring=False, remove_sessions=True):
        """Edit a holiday. Optionally removes untouched sessions on the new date."""
        existing = db.session.execute(
            text("SELECT id, name, date FROM holidays WHERE id = :id"), {'id': holiday_id}
        ).mappings().first()
        if not existing:
            return False, "Holiday not found"

        name = (name or '').strip()
        if not name:
            return False, "Holiday name is required"
        if len(name) > 200:
            return False, "Holiday name is too long (max 200 characters)"
        try:
            hdate = _to_date(holiday_date)
        except ValueError:
            return False, "Enter a valid date"
        if hdate is None:
            return False, "Date is required"

        if self._holiday_exists(hdate, name, exclude_id=holiday_id):
            return False, f"{name} is already recorded for {hdate.isoformat()}"

        old_date = _to_date(existing['date'])
        removed = 0
        try:
            db.session.execute(text("""
                UPDATE holidays
                SET name = :name, date = :date, description = :description,
                    is_recurring = :recurring
                WHERE id = :id
            """), {
                'name': name, 'date': hdate.isoformat(),
                'description': (description or '').strip() or None,
                'recurring': 1 if is_recurring else 0, 'id': holiday_id,
            })
            if remove_sessions:
                removed, _ = self._purge_untouched("s.date = :d", {'d': hdate.isoformat()})
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Holiday update error: {str(e)}")
            return False, "Failed to update holiday"

        self._log_admin_activity(
            admin_username, ActivityType.SETTINGS_CHANGED,
            f"Updated holiday {holiday_id} '{name}' ({old_date} -> {hdate}); "
            f"{removed} session(s) removed"
        )
        message = f"{name} updated."
        if remove_sessions:
            message += f" {removed} untouched scheduled session(s) removed."
        if old_date and old_date != hdate:
            message += (" Sessions removed earlier for the old date are not restored "
                        "automatically; run Generate sessions if you need them back.")
        return True, message

    def delete_holiday(self, admin_username, holiday_id):
        """Delete a holiday. Removed sessions are not restored automatically."""
        existing = db.session.execute(
            text("SELECT id, name, date FROM holidays WHERE id = :id"), {'id': holiday_id}
        ).mappings().first()
        if not existing:
            return False, "Holiday not found"

        try:
            db.session.execute(text("DELETE FROM holidays WHERE id = :id"), {'id': holiday_id})
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Holiday delete error: {str(e)}")
            return False, "Failed to delete holiday"

        self._log_admin_activity(
            admin_username, ActivityType.SETTINGS_CHANGED,
            f"Deleted holiday {holiday_id} '{existing['name']}' ({existing['date']})"
        )
        return True, (f"{existing['name']} deleted. Run Generate sessions if sessions "
                      "should now exist on that date.")

    def copy_holidays(self, admin_username, from_year, to_year):
        """
        Copy one-off holidays from one year to another, same month and day.
        Movable holidays (Easter, Eid...) fall on different dates: check them.
        Recurring holidays already apply every year and are skipped.
        """
        if from_year == to_year:
            return False, "Choose two different years"
        if not (2000 <= from_year <= 2100 and 2000 <= to_year <= 2100):
            return False, "Years must be between 2000 and 2100"

        source = [h for h in self.list_holidays(from_year) if not h['is_recurring']]
        if not source:
            return False, f"No one-off holidays found in {from_year}"

        created = skipped = 0
        try:
            for h in source:
                try:
                    new_date = date(to_year, h['date'].month, h['date'].day)
                except ValueError:  # 29 Feb into a non-leap year
                    skipped += 1
                    continue
                if self._holiday_exists(new_date, h['name']):
                    skipped += 1
                    continue
                db.session.execute(text("""
                    INSERT INTO holidays (name, date, description, is_recurring, created_at)
                    VALUES (:name, :date, :description, 0, :created)
                """), {
                    'name': h['name'], 'date': new_date.isoformat(),
                    'description': h['description'],
                    'created': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                })
                created += 1
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Holiday copy error: {str(e)}")
            return False, "Failed to copy holidays"

        self._log_admin_activity(
            admin_username, ActivityType.SETTINGS_CHANGED,
            f"Copied holidays {from_year} -> {to_year}: {created} created, {skipped} skipped"
        )
        return True, (f"{created} holiday(s) copied from {from_year} to {to_year}"
                      f"{f', {skipped} skipped' if skipped else ''}. "
                      "Check movable holidays such as Easter and Eid.")

    # ==================================================================
    # Session generation
    # ==================================================================

    def generation_defaults(self):
        """Form defaults for the Generate page."""
        today = _today()
        sem = get_current_semester()
        window_start, window_end = semester_window(sem, today)

        expired = db.session.execute(text("""
            SELECT COUNT(*) FROM timetable t
            JOIN classes c ON c.class_id = t.class_id
            WHERE t.is_active = 1 AND c.is_active = 1 AND c.semester = :sem
              AND t.effective_to IS NOT NULL AND t.effective_to < :end
        """), {'sem': sem, 'end': window_end.isoformat()}).scalar() or 0

        return {
            'semester': sem,
            'start_date': max(today, window_start),
            'end_date': window_end,
            'roll_expired': expired > 0,
            'expired_count': expired,
        }

    def plan_generation(self, start_date, end_date, semester=None, course_code=None,
                        class_id=None, roll_expired=False):
        """
        Work out what generation would do, without writing anything.

        Scope: one class (class_id), else one course (course_code), else every
        class of `semester` (default: the current campus semester).

        Entries whose effective range ended before `end_date` are 'expired'.
        With roll_expired they are rolled forward to the semester window (and
        that change is saved when the plan is executed); without it they only
        produce sessions inside their original range.

        Returns a dict. plan['ok'] is False with plan['error'] set if the
        request is invalid.
        """
        plan = {
            'ok': False, 'error': None, 'to_create': [], 'total': 0,
            'skipped_holiday': 0, 'holiday_hits': [], 'duplicates': 0,
            'skipped_no_lecturer': 0, 'no_lecturer_classes': [],
            'skipped_past': 0, 'skipped_expired': 0, 'not_started': 0,
            'conflicts': [], 'expired_entries': [], 'per_class': [],
            'sample': [], 'entries_considered': 0, 'semester': None,
            'scope_label': '', 'start': None, 'end': None,
            'roll_expired': bool(roll_expired),
        }

        try:
            start, end = _to_date(start_date), _to_date(end_date)
        except ValueError:
            plan['error'] = "Enter valid start and end dates"
            return plan
        if start is None or end is None:
            plan['error'] = "Start and end dates are required"
            return plan

        today = _today()
        if start < today:
            plan['error'] = ("The start date can't be in the past: sessions are "
                             "never back-filled. Use today or later.")
            return plan
        if end < start:
            plan['error'] = "The end date can't be before the start date"
            return plan
        if (end - start).days > MAX_GENERATION_DAYS:
            plan['error'] = f"Choose a range of at most {MAX_GENERATION_DAYS} days"
            return plan

        where = ["t.is_active = 1", "c.is_active = 1"]
        params = {}
        if class_id:
            cls = self._get_class_row(class_id)
            if not cls:
                plan['error'] = "Class not found"
                return plan
            where.append("t.class_id = :cid")
            params['cid'] = class_id
            plan['semester'] = cls['semester']
            plan['scope_label'] = f"Class {class_id}"
        else:
            sem = _sem_int(semester) if semester else get_current_semester()
            if sem not in (1, 2):
                plan['error'] = "Semester must be 1 or 2"
                return plan
            where.append("c.semester = :sem")
            params['sem'] = sem
            plan['semester'] = sem
            if course_code:
                where.append("c.course_code = :course")
                params['course'] = course_code
                plan['scope_label'] = f"Course {course_code}, semester {sem}"
            else:
                plan['scope_label'] = f"All classes, semester {sem}"

        entries = self._load_entries(" AND ".join(where), params)
        plan['entries_considered'] = len(entries)
        plan['start'], plan['end'] = start, end

        # Effective window per entry (rolled forward when asked)
        roll_from, roll_to = semester_window(plan['semester'], start)
        roll_to = max(roll_to, end)
        by_dow = {}
        for e in entries:
            expired = e['effective_to'] is not None and e['effective_to'] < end
            e['window'] = (e['effective_from'], e['effective_to'])
            e['rolled'] = False
            if expired:
                plan['expired_entries'].append(e)
                if roll_expired:
                    e['window'] = (roll_from, roll_to)
                    e['rolled'] = True
            by_dow.setdefault(e['day_of_week'], []).append(e)
        for items in by_dow.values():
            items.sort(key=lambda e: (e['start_time'], e['class_id']))

        holidays = self._holiday_map(start, end)

        # Existing sessions in range: duplicates and lecturer load
        existing_keys, existing_by_class_day, busy = set(), {}, {}
        rows = db.session.execute(text(
            "SELECT class_id, date, start_time, end_time, status, created_by "
            "FROM class_sessions WHERE date >= :s AND date <= :e"
        ), {'s': start.isoformat(), 'e': end.isoformat()}).mappings().all()
        for r in rows:
            ds = str(r['date'])[:10]
            existing_keys.add((r['class_id'], ds, r['start_time']))
            if r['status'] not in _OPEN_STATES:
                existing_by_class_day.setdefault((r['class_id'], ds), []).append(
                    (r['start_time'], r['end_time'])
                )
                if r['created_by']:
                    busy.setdefault((r['created_by'], ds), []).append(
                        (r['start_time'], r['end_time'])
                    )

        lecturers = self._lecturers_by_class()

        def primary(cid):
            return next((l for l in lecturers.get(cid, []) if l['is_active']), None)

        planned_keys, no_lecturer, holiday_hits = set(), set(), {}
        now_hm = _now_hm()

        day = start
        while day <= end:
            ds = day.isoformat()
            for e in by_dow.get((day.weekday() + 1) % 7, []):
                win_from, win_to = e['window']
                if win_from and day < win_from:
                    plan['not_started'] += 1
                    continue
                if win_to and day > win_to:
                    plan['skipped_expired'] += 1
                    continue
                if day in holidays:
                    plan['skipped_holiday'] += 1
                    holiday_hits[day] = holidays[day]
                    continue
                if day == today and e['start_time'] <= now_hm:
                    plan['skipped_past'] += 1
                    continue

                key = (e['class_id'], ds, e['start_time'])
                if key in existing_keys or key in planned_keys:
                    plan['duplicates'] += 1
                    continue

                if any(_times_overlap(e['start_time'], e['end_time'], st, et)
                       for st, et in existing_by_class_day.get((e['class_id'], ds), [])):
                    plan['conflicts'].append({
                        'class_id': e['class_id'], 'date': day,
                        'start_time': e['start_time'],
                        'reason': "Overlaps an existing session of the same class",
                    })
                    continue

                lecturer = primary(e['class_id'])
                if not lecturer:
                    no_lecturer.add(e['class_id'])
                    plan['skipped_no_lecturer'] += 1
                    continue

                lec_id = lecturer['instructor_id']
                if any(_times_overlap(e['start_time'], e['end_time'], st, et)
                       for st, et in busy.get((lec_id, ds), [])):
                    plan['conflicts'].append({
                        'class_id': e['class_id'], 'date': day,
                        'start_time': e['start_time'],
                        'reason': f"{lecturer['instructor_name']} already has a session then",
                    })
                    continue

                planned_keys.add(key)
                busy.setdefault((lec_id, ds), []).append((e['start_time'], e['end_time']))
                plan['to_create'].append({
                    'class_id': e['class_id'], 'date': ds, 'day': day,
                    'start_time': e['start_time'], 'end_time': e['end_time'],
                    'created_by': lec_id, 'lecturer': lecturer['instructor_name'],
                })
            day += timedelta(days=1)

        counts = {}
        for row in plan['to_create']:
            counts[row['class_id']] = counts.get(row['class_id'], 0) + 1

        plan['total'] = len(plan['to_create'])
        plan['per_class'] = sorted(counts.items())
        plan['sample'] = plan['to_create'][:20]
        plan['no_lecturer_classes'] = sorted(no_lecturer)
        plan['holiday_hits'] = sorted(holiday_hits.items())
        plan['ok'] = True
        return plan

    def generate_sessions(self, admin_username, start_date, end_date, semester=None,
                          course_code=None, class_id=None, roll_expired=False):
        """
        Plan again (never trusting an earlier preview) and write the sessions.

        Returns (success, message, plan).
        """
        plan = self.plan_generation(
            start_date, end_date, semester=semester, course_code=course_code,
            class_id=class_id, roll_expired=roll_expired
        )
        if not plan['ok']:
            return False, plan['error'], plan

        try:
            rolled = self._execute_plan(plan)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Session generation error: {str(e)}")
            return False, "Session generation failed; nothing was changed", plan

        self._log_admin_activity(
            admin_username, ActivityType.SESSION_CREATED,
            f"Generated {plan['total']} session(s) {plan['start']} to {plan['end']} "
            f"({plan['scope_label']}); {rolled} timetable entr(ies) rolled forward"
        )

        message = f"{plan['total']} session(s) generated for {plan['scope_label']}."
        if rolled:
            message += f" {rolled} expired timetable entr(ies) rolled forward."
        return True, message, plan

    # ==================================================================
    # Internals
    # ==================================================================

    def _execute_plan(self, plan):
        """Write a plan's sessions (and entry roll-forwards). No commit here."""
        rolled = 0
        for e in plan['expired_entries']:
            if e.get('rolled'):
                new_from, new_to = e['window']
                db.session.execute(text(
                    "UPDATE timetable SET effective_from = :f, effective_to = :t WHERE id = :id"
                ), {'f': new_from.isoformat(), 't': new_to.isoformat(), 'id': e['id']})
                rolled += 1

        if plan['to_create']:
            stamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            db.session.execute(text("""
                INSERT INTO class_sessions
                    (class_id, date, start_time, end_time, status, created_by,
                     session_notes, attendance_count, total_students,
                     created_at, updated_at)
                VALUES
                    (:class_id, :date, :start_time, :end_time, 'scheduled', :created_by,
                     'Auto-generated from timetable', 0, 0, :stamp, :stamp)
            """), [
                {
                    'class_id': r['class_id'], 'date': r['date'],
                    'start_time': r['start_time'], 'end_time': r['end_time'],
                    'created_by': r['created_by'], 'stamp': stamp,
                }
                for r in plan['to_create']
            ])
        return rolled

    def _recreate_in_same_weeks(self, class_id, removed_dates, day_of_week,
                                start_time, end_time):
        """
        Replace removed sessions one-for-one on a new slot: each removed session
        gets a replacement in the SAME week (Monday-Sunday) on the new weekday.
        Weeks that kept a held or started session therefore get nothing extra,
        and the semester's length never changes. Replacements still obey
        holidays, the entry's dates, clashes and "never in the past".
        Returns the number created. No commit here.
        """
        targets = set()
        for d in removed_dates:
            monday = d - timedelta(days=d.weekday())
            targets.add(monday + timedelta(days=(int(day_of_week) - 1) % 7))
        if not targets:
            return 0

        start = max(_today(), min(targets))
        end = max(targets)
        if end < start:
            return 0

        plan = self.plan_generation(start, end, class_id=class_id)
        if not plan['ok']:
            return 0
        wanted = {t.isoformat() for t in targets}
        plan['to_create'] = [
            r for r in plan['to_create']
            if r['date'] in wanted
            and r['start_time'] == start_time and r['end_time'] == end_time
        ]
        plan['total'] = len(plan['to_create'])
        self._execute_plan(plan)
        return plan['total']

    def _purge_slot_sessions(self, class_id, day_of_week, start_time, end_time):
        """Remove future untouched sessions of one slot. Returns (count, dates)."""
        return self._purge_untouched(
            "s.class_id = :cid "
            "AND CAST(strftime('%w', s.date) AS INTEGER) = :dow "
            "AND s.start_time = :st AND s.end_time = :et "
            "AND s.date >= :today AND (s.date > :today OR s.start_time > :now)",
            {
                'cid': class_id, 'dow': int(day_of_week), 'st': start_time,
                'et': end_time, 'today': _today().isoformat(), 'now': _now_hm(),
            }
        )

    def _purge_untouched(self, extra_where, params):
        """
        Delete untouched sessions matching a filter. Returns (count, dates), the
        dates being those of the removed sessions. No commit here: callers
        commit so the change is atomic with their own.
        """
        rows = db.session.execute(text(
            f"SELECT s.session_id, s.date FROM class_sessions s "
            f"WHERE {extra_where} AND {_UNTOUCHED_SQL}"
        ), params).fetchall()
        if not rows:
            return 0, []

        ids = [r[0] for r in rows]
        db.session.execute(
            text("DELETE FROM class_sessions WHERE session_id IN :ids")
            .bindparams(bindparam('ids', expanding=True)),
            {'ids': ids}
        )
        return len(ids), sorted(_to_date(r[1]) for r in rows)

    @staticmethod
    def _find_issues(entries):
        """
        Every clash among `entries`, as {'kind', 'a', 'b', 'who'}: kind is
        'class' (one class twice), 'lecturer' (shared lecturer) or 'cohort'
        (same course + year). Only same-semester, same-day entries whose time
        AND effective-date ranges overlap are compared.
        """
        by_day = {}
        for e in entries:
            by_day.setdefault((e['day_of_week'], e['semester']), []).append(e)

        issues = []
        for items in by_day.values():
            items.sort(key=lambda e: (_minutes(e['start_time']), e['class_id']))
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    if _minutes(b['start_time']) >= _minutes(a['end_time']):
                        break  # sorted by start: nothing later can overlap `a`
                    if not _dates_overlap(a['effective_from'], a['effective_to'],
                                          b['effective_from'], b['effective_to']):
                        continue

                    if a['class_id'] == b['class_id']:
                        issues.append({'kind': 'class', 'a': a, 'b': b,
                                       'who': a['class_id']})
                        continue

                    shared = a['lecturer_ids'] & b['lecturer_ids']
                    if shared:
                        names = ', '.join(
                            l['instructor_name'] for l in a['lecturers']
                            if l['instructor_id'] in shared
                        )
                        issues.append({'kind': 'lecturer', 'a': a, 'b': b, 'who': names})

                    if (a['course_code'], a['year']) == (b['course_code'], b['year']):
                        issues.append({
                            'kind': 'cohort', 'a': a, 'b': b,
                            'who': f"{a['course_code']} year {a['year']}",
                        })

        issues.sort(key=lambda x: (
            x['kind'], DAY_ORDER.index(x['a']['day_of_week']), x['a']['start_time']
        ))
        return issues

    def _holiday_map(self, start, end):
        """{date: name} for every holiday in range, recurring ones included."""
        result = {}
        rows = db.session.execute(text("SELECT name, date, is_recurring FROM holidays")).fetchall()
        for name, raw_date, recurring in rows:
            try:
                hdate = _to_date(raw_date)
            except ValueError:
                continue
            if hdate is None:
                continue
            if start <= hdate <= end:
                result.setdefault(hdate, name)
            if recurring:
                for year in range(start.year, end.year + 1):
                    try:
                        occurrence = date(year, hdate.month, hdate.day)
                    except ValueError:
                        continue
                    if start <= occurrence <= end:
                        result.setdefault(occurrence, name)
        return result

    def _holiday_exists(self, hdate, name, exclude_id=None):
        sql = "SELECT 1 FROM holidays WHERE date = :d AND lower(name) = lower(:n)"
        params = {'d': hdate.isoformat(), 'n': name}
        if exclude_id:
            sql += " AND id <> :id"
            params['id'] = exclude_id
        return db.session.execute(text(sql), params).first() is not None

    def _get_class_row(self, class_id):
        row = db.session.execute(text(
            "SELECT class_id, class_name, course_code, year, semester, is_active "
            "FROM classes WHERE class_id = :cid"
        ), {'cid': class_id}).mappings().first()
        if not row:
            return None
        cls = dict(row)
        cls['semester'] = _sem_int(cls['semester'])
        cls['is_active'] = bool(cls['is_active'])
        return cls

    def _lecturers_by_class(self):
        """{class_id: [lecturers]}, earliest-assigned first."""
        rows = db.session.execute(text("""
            SELECT ci.class_id, ci.instructor_id, i.instructor_name, i.is_active
            FROM class_instructors ci
            LEFT JOIN instructors i ON i.instructor_id = ci.instructor_id
            ORDER BY (ci.assigned_date IS NULL), ci.assigned_date, ci.id
        """)).mappings().all()

        result = {}
        for r in rows:
            result.setdefault(r['class_id'], []).append({
                'instructor_id': r['instructor_id'],
                'instructor_name': r['instructor_name'] or r['instructor_id'],
                'is_active': bool(r['is_active']),
            })
        return result

    def _load_entries(self, where="", params=None):
        """Timetable entries joined to their class, with lecturers attached."""
        sql = """
            SELECT t.id, t.class_id, t.day_of_week, t.start_time, t.end_time,
                   t.is_active, t.effective_from, t.effective_to,
                   c.class_name, c.course_code, c.year, c.semester,
                   c.is_active AS class_active
            FROM timetable t
            JOIN classes c ON c.class_id = t.class_id
        """
        if where:
            sql += f" WHERE {where}"

        rows = db.session.execute(text(sql), params or {}).mappings().all()
        lecturers = self._lecturers_by_class()

        entries = []
        for r in rows:
            e = dict(r)
            e['is_active'] = bool(e['is_active'])
            e['class_active'] = bool(e['class_active'])
            e['semester'] = _sem_int(e['semester'])
            e['effective_from'] = _to_date(e['effective_from'])
            e['effective_to'] = _to_date(e['effective_to'])
            e['day_name'] = DAY_NAMES.get(e['day_of_week'], '?')
            e['lecturers'] = lecturers.get(e['class_id'], [])
            e['lecturer_ids'] = {l['instructor_id'] for l in e['lecturers']}
            entries.append(e)

        entries.sort(key=lambda e: (
            DAY_ORDER.index(e['day_of_week']), e['start_time'], e['class_id']
        ))
        return entries

    def _clean_slot(self, class_id, day_of_week, start_time, end_time,
                    effective_from, effective_to, require_class_active=True):
        """Validate form values. Returns (error, cleaned) - one of them is None."""
        class_id = (class_id or '').strip()
        cls = self._get_class_row(class_id) if class_id else None
        if not cls:
            return "Choose a class", None
        if require_class_active and not cls['is_active']:
            return "That class is inactive", None

        try:
            day = int(day_of_week)
        except (TypeError, ValueError):
            return "Choose a day of the week", None
        if not 0 <= day <= 6:
            return "Choose a day of the week", None

        try:
            start, end = _norm_time(start_time), _norm_time(end_time)
        except ValueError:
            return "Enter valid start and end times", None
        if _minutes(end) <= _minutes(start):
            return "End time must be after start time", None

        try:
            eff_from, eff_to = _to_date(effective_from), _to_date(effective_to)
        except ValueError:
            return "Enter valid effective dates", None
        if eff_from is None:
            return "Effective-from date is required", None
        if eff_to is not None and eff_to < eff_from:
            return "Effective-to can't be before effective-from", None

        return None, {
            'class_id': class_id, 'day': day, 'start': start, 'end': end,
            'from': eff_from, 'to': eff_to,
        }

    def _log_admin_activity(self, admin_username, activity_type, description):
        """Log an action under the admin's own identity (user_type='admin')."""
        try:
            db.session.execute(text("""
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (:user_id, :user_type, :activity_type, :description, :ts)
            """), {
                'user_id': admin_username, 'user_type': UserType.ADMIN,
                'activity_type': activity_type, 'description': description,
                'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            })
            db.session.commit()
        except Exception as e:
            logger.error(f"Admin activity logging error: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass