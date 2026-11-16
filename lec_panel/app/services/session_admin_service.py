"""
Session Admin Service (Phase 6a)
Campus-wide oversight of class sessions: filtered list, session detail, cancel
or reschedule a single not-yet-held session, and the lecturer dismissal log.

Design notes (match the live data, not the ORM):

- Plain ``text()`` SQL, exactly like TimetableAdminService: sessions are stored
  as text ('2026-11-09', '15:00') and every date/time comparison that matters
  is done in Python on normalised values, so legacy 'HH:MM:SS' rows still work.

- The admin owns the timetable and generates the sessions. The lecturer panel
  is no longer the place sessions are created, so nothing here goes through
  SessionService.

- A session may be cancelled or moved only while it is UNTOUCHED (same
  definition as the timetable): status 'scheduled', no attendance, dismissal or
  metric rows, and it has not started yet. Anything else is read-only here.

- Rescheduling never moves a row. The original is kept as 'cancelled' (with a
  note saying where it went) and a NEW scheduled session is created. This is
  deliberate: session generation treats ANY existing row for a class + date +
  start time as a duplicate, so the cancelled original keeps the old slot from
  being regenerated. Both changes happen in one transaction.

- Clashes are hard blocks and are checked against sessions of that day that
  occupy time (scheduled / ongoing / completed): the same class, any lecturer
  assigned to the class, and the same cohort (course + year).

- Cancelled and dismissed sessions from older data often have no row in
  session_dismissals. The admin cancel does not write one either: that table's
  instructor_id is a foreign key to instructors and the admin is not one. The
  reason lives in session_notes and in the activity log instead.

Methods that change data return (success, message[, extra]) tuples.
"""

from datetime import date, datetime
import logging

from sqlalchemy import text

from app import db
from app.services.timetable_admin_service import (
    TimetableAdminService, _UNTOUCHED_SQL, _minutes, _norm_time,
    _times_overlap, _to_date,
)
from config.constants import ActivityType, UserType

logger = logging.getLogger(__name__)

# 'missed' is allowed by the schema but is not in config.constants.SessionStatus
STATUSES = ('scheduled', 'ongoing', 'completed', 'missed', 'dismissed', 'cancelled')
STATUS_LABELS = {
    'scheduled': 'Scheduled', 'ongoing': 'Ongoing', 'completed': 'Completed',
    'missed': 'Missed', 'dismissed': 'Dismissed', 'cancelled': 'Cancelled',
}
STATUS_BADGES = {
    'scheduled': 'info', 'ongoing': 'success', 'completed': 'secondary',
    'missed': 'dark', 'dismissed': 'warning', 'cancelled': 'danger',
}
DISMISSAL_STATUSES = ('dismissed', 'rescheduled', 'cancelled')

# Sessions that take up a lecturer's / class's / cohort's time
_OCCUPYING = ('scheduled', 'ongoing', 'completed')

MAX_REASON = 300
DEFAULT_PER_PAGE = 50


def _hm(value):
    """'HH:MM' from 'HH:MM', 'HH:MM:SS' or a time object; '' when empty."""
    return str(value)[:5] if value not in (None, '') else ''


def _safe_date(value):
    try:
        return _to_date(value)
    except ValueError:
        return None


def _start_dt(date_value, start_time):
    """The session's start as a datetime, or None if it can't be read."""
    d = _safe_date(date_value)
    if d is None:
        return None
    try:
        hh, mm = _norm_time(start_time).split(':')
    except ValueError:
        return None
    return datetime(d.year, d.month, d.day, int(hh), int(mm))


def _now():
    return datetime.now()


def _ts():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def _nice_date(d):
    return d.strftime('%a %d %b %Y') if d else '?'


def _append_note(existing, line):
    return f"{existing}\n{line}" if existing else line


class SessionAdminService:
    """Admin oversight of campus sessions."""

    def __init__(self):
        self._tt = TimetableAdminService()

    # ==================================================================
    # Reference data
    # ==================================================================

    def get_filter_options(self):
        """Active courses and lecturers for the filter dropdowns."""
        return self._tt.get_filter_options()

    # ==================================================================
    # Listing
    # ==================================================================

    @staticmethod
    def _filters(date_from, date_to, course_code, year, class_id, instructor_id):
        """WHERE clauses (without status) and their parameters."""
        where, params = [], {}
        if date_from:
            where.append("substr(s.date, 1, 10) >= :df")
            params['df'] = date_from.isoformat()
        if date_to:
            where.append("substr(s.date, 1, 10) <= :dt")
            params['dt'] = date_to.isoformat()
        if course_code:
            where.append("c.course_code = :course")
            params['course'] = course_code
        if year:
            where.append("c.year = :year")
            params['year'] = int(year)
        if class_id:
            where.append("s.class_id LIKE :cid")
            params['cid'] = f"%{class_id}%"
        if instructor_id:
            where.append(
                "EXISTS (SELECT 1 FROM class_instructors ci "
                "WHERE ci.class_id = s.class_id AND ci.instructor_id = :iid)"
            )
            params['iid'] = instructor_id
        return where, params

    def list_sessions(self, date_from=None, date_to=None, course_code=None, year=None,
                      class_id=None, instructor_id=None, status=None, order='asc',
                      page=1, per_page=DEFAULT_PER_PAGE):
        """
        One page of sessions, campus-wide (no instructor restriction).

        Returns {'rows', 'total', 'page', 'pages', 'per_page', 'status_counts'}.
        status_counts ignores the status filter so the chips always show how the
        rest of the filtered set splits up.
        """
        where, params = self._filters(
            date_from, date_to, course_code, year, class_id, instructor_id
        )
        base_where = f"WHERE {' AND '.join(where)}" if where else ""

        count_rows = db.session.execute(text(
            "SELECT s.status AS status, COUNT(*) AS n FROM class_sessions s "
            "LEFT JOIN classes c ON c.class_id = s.class_id "
            f"{base_where} GROUP BY s.status"
        ), params).mappings().all()
        status_counts = {r['status']: r['n'] for r in count_rows}
        total_all = sum(status_counts.values())

        page_where, page_params = list(where), dict(params)
        if status in STATUSES:
            page_where.append("s.status = :status")
            page_params['status'] = status
            total = status_counts.get(status, 0)
        else:
            status = None
            total = total_all

        per_page = max(1, int(per_page))
        pages = max(1, -(-total // per_page))
        page = min(max(1, int(page)), pages)
        direction = 'DESC' if order == 'desc' else 'ASC'

        rows = db.session.execute(text(f"""
            SELECT s.session_id, s.class_id, s.date, s.start_time, s.end_time,
                   s.status, s.created_by, s.attendance_count, s.total_students,
                   c.class_name, c.course_code, c.year
            FROM class_sessions s
            LEFT JOIN classes c ON c.class_id = s.class_id
            {"WHERE " + " AND ".join(page_where) if page_where else ""}
            ORDER BY substr(s.date, 1, 10) {direction}, s.start_time {direction},
                     s.class_id, s.session_id
            LIMIT :limit OFFSET :offset
        """), dict(page_params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()

        lecturers = self._lecturers_by_class()
        now = _now()
        items = []
        for r in rows:
            d = _safe_date(r['date'])
            start_dt = _start_dt(r['date'], r['start_time'])
            names = [l['instructor_name'] for l in lecturers.get(r['class_id'], [])
                     if l['is_active']] or [
                l['instructor_name'] for l in lecturers.get(r['class_id'], [])
            ]
            items.append({
                'session_id': r['session_id'],
                'class_id': r['class_id'],
                'class_name': r['class_name'] or '',
                'course_code': r['course_code'] or '',
                'year': r['year'],
                'date': d,
                'date_raw': str(r['date'])[:10],
                'day_label': d.strftime('%a') if d else '',
                'start_time': _hm(r['start_time']),
                'end_time': _hm(r['end_time']),
                'status': r['status'],
                'attendance_count': r['attendance_count'] or 0,
                'total_students': r['total_students'] or 0,
                'lecturers': names,
                'is_past': bool(start_dt and start_dt < now),
            })

        return {
            'rows': items, 'total': total, 'page': page, 'pages': pages,
            'per_page': per_page, 'status_counts': status_counts,
            'total_all': total_all,
        }

    # ==================================================================
    # Detail
    # ==================================================================

    def get_session(self, session_id):
        """Everything the detail page needs, or None if there is no such session."""
        row = self._get_row(session_id)
        if not row:
            return None

        d = _safe_date(row['date'])
        start, end = _hm(row['start_time']), _hm(row['end_time'])
        try:
            duration = _minutes(end) - _minutes(start)
        except ValueError:
            duration = None
        start_dt = _start_dt(row['date'], row['start_time'])
        now = _now()

        lecturers = self._lecturers_for_class(row['class_id'])
        creator = db.session.execute(text(
            "SELECT instructor_name FROM instructors WHERE instructor_id = :i"
        ), {'i': row['created_by']}).scalar() if row['created_by'] else None

        att_rows = db.session.execute(text(
            "SELECT status, COUNT(*) AS n FROM attendance "
            "WHERE session_id = :id GROUP BY status"
        ), {'id': session_id}).mappings().all()
        attendance = {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}
        for a in att_rows:
            attendance[a['status']] = attendance.get(a['status'], 0) + a['n']
        attendance['total'] = sum(attendance.values())

        dismissals = db.session.execute(text("""
            SELECT d.id, d.instructor_id, i.instructor_name, d.reason, d.dismissal_time,
                   d.rescheduled_to, d.rescheduled_time, d.notes, d.status
            FROM session_dismissals d
            LEFT JOIN instructors i ON i.instructor_id = d.instructor_id
            WHERE d.session_id = :id ORDER BY d.dismissal_time DESC
        """), {'id': session_id}).mappings().all()

        can_modify, reason = self._modifiable(row)
        holiday = None
        if d:
            holiday = self._tt._holiday_map(d, d).get(d)

        return {
            'session_id': row['session_id'],
            'class_id': row['class_id'],
            'class_name': row['class_name'] or '',
            'course_code': row['course_code'] or '',
            'course_name': row['course_name'] or '',
            'year': row['year'],
            'semester': row['semester'],
            'class_active': bool(row['class_active']) if row['class_active'] is not None else True,
            'date': d,
            'date_raw': str(row['date'])[:10],
            'day_name': d.strftime('%A') if d else '',
            'start_time': start, 'end_time': end, 'duration': duration,
            'status': row['status'],
            'created_by': row['created_by'],
            'created_by_name': creator or row['created_by'] or '',
            'created_at': row['created_at'], 'updated_at': row['updated_at'],
            'attendance_count': row['attendance_count'] or 0,
            'total_students': row['total_students'] or 0,
            'notes': row['session_notes'] or '',
            'lecturers': lecturers,
            'attendance': attendance,
            'dismissals': [dict(x) for x in dismissals],
            'is_past': bool(start_dt and start_dt < now),
            'holiday': holiday,
            'can_modify': can_modify,
            'cannot_modify_reason': None if can_modify else reason,
        }

    # ==================================================================
    # Cancel / reschedule
    # ==================================================================

    def cancel_session(self, admin_username, session_id, reason, notify=True):
        """Cancel one untouched upcoming session. Returns (success, message)."""
        reason = (reason or '').strip()
        if not reason:
            return False, "Give a reason for cancelling"
        if len(reason) > MAX_REASON:
            return False, f"Keep the reason under {MAX_REASON} characters"

        row = self._get_row(session_id)
        if not row:
            return False, "Session not found"
        ok, why = self._modifiable(row)
        if not ok:
            return False, why

        d = _safe_date(row['date'])
        label = f"{row['class_id']} on {_nice_date(d)} {_hm(row['start_time'])}"
        note = (f"Cancelled by admin {admin_username} on "
                f"{date.today().isoformat()}: {reason}")
        try:
            result = db.session.execute(text("""
                UPDATE class_sessions
                SET status = 'cancelled', session_notes = :notes, updated_at = :ts
                WHERE session_id = :id AND status = 'scheduled'
            """), {'notes': _append_note(row['session_notes'], note),
                   'ts': _ts(), 'id': session_id})
            if result.rowcount != 1:
                db.session.rollback()
                return False, "That session changed while you were working: reload it and try again"
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Cancel session error: {e}")
            return False, "Could not cancel the session"

        self._log_admin_activity(
            admin_username, ActivityType.SESSION_DISMISSED,
            f"Admin cancelled session {session_id} ({label}). Reason: {reason}"
        )
        if notify:
            self._notify_lecturers(
                row['class_id'], f"Session cancelled: {row['class_id']}",
                f"The session on {_nice_date(d)} at {_hm(row['start_time'])} was "
                f"cancelled by the administrator. Reason: {reason}", session_id
            )
        return True, f"Session {label} cancelled"

    def check_move(self, session_id, new_date, start_time, end_time):
        """
        Everything that would stop (or deserve a warning on) a move, without
        writing. Returns {'error': str|None, 'conflicts': [str], 'holiday': str|None}.
        'error' is a blocking problem that is not a clash.
        """
        result = {'error': None, 'conflicts': [], 'holiday': None}
        row = self._get_row(session_id)
        if not row:
            result['error'] = "Session not found"
            return result
        ok, why = self._modifiable(row)
        if not ok:
            result['error'] = why
            return result

        error, cleaned = self._parse_move(new_date, start_time, end_time)
        if error:
            result['error'] = error
            return result

        starts = datetime(cleaned['date'].year, cleaned['date'].month, cleaned['date'].day,
                          *map(int, cleaned['start'].split(':')))
        if starts <= _now():
            result['error'] = "The new time has to be in the future"
            return result
        if (cleaned['date'].isoformat() == str(row['date'])[:10]
                and cleaned['start'] == _hm(row['start_time'])
                and cleaned['end'] == _hm(row['end_time'])):
            result['error'] = "That is the session's current time"
            return result

        result['holiday'] = self._tt._holiday_map(cleaned['date'], cleaned['date']).get(cleaned['date'])
        result['conflicts'] = [
            c['message'] for c in self.find_conflicts(
                row['class_id'], cleaned['date'], cleaned['start'], cleaned['end'],
                exclude_id=session_id
            )
        ]
        return result

    def reschedule_session(self, admin_username, session_id, new_date, start_time,
                           end_time, reason, allow_holiday=False, notify=True):
        """
        Move one untouched upcoming session. The original is kept as
        'cancelled' and a new scheduled session is created, in one transaction.
        Returns (success, message[, new_session_id]).
        """
        reason = (reason or '').strip()
        if not reason:
            return False, "Give a reason for the change"
        if len(reason) > MAX_REASON:
            return False, f"Keep the reason under {MAX_REASON} characters"

        row = self._get_row(session_id)
        if not row:
            return False, "Session not found"
        if row['class_active'] is not None and not row['class_active']:
            return False, "That class is inactive: reactivate it before moving its sessions"

        check = self.check_move(session_id, new_date, start_time, end_time)
        if check['error']:
            return False, check['error']
        if check['conflicts']:
            return False, TimetableAdminService.format_conflicts(
                [{'message': m} for m in check['conflicts']]
            )
        if check['holiday'] and not allow_holiday:
            return False, (f"The new date is a holiday ({check['holiday']}). "
                           f"Tick 'Allow on a holiday' if that is intended")

        _, cleaned = self._parse_move(new_date, start_time, end_time)
        old_d = _safe_date(row['date'])
        old_label = f"{_nice_date(old_d)} {_hm(row['start_time'])}-{_hm(row['end_time'])}"
        new_label = f"{_nice_date(cleaned['date'])} {cleaned['start']}-{cleaned['end']}"
        today = date.today().isoformat()

        try:
            result = db.session.execute(text("""
                UPDATE class_sessions
                SET status = 'cancelled', session_notes = :notes, updated_at = :ts
                WHERE session_id = :id AND status = 'scheduled'
            """), {
                'notes': _append_note(
                    row['session_notes'],
                    f"Rescheduled by admin {admin_username} on {today} to {new_label}. "
                    f"Reason: {reason}"),
                'ts': _ts(), 'id': session_id,
            })
            if result.rowcount != 1:
                db.session.rollback()
                return False, "That session changed while you were working: reload it and try again"

            ts = _ts()
            insert = db.session.execute(text("""
                INSERT INTO class_sessions
                    (class_id, date, start_time, end_time, status, created_by,
                     created_at, updated_at, attendance_count, total_students,
                     session_notes)
                VALUES
                    (:class_id, :date, :start, :end, 'scheduled', :created_by,
                     :ts, :ts, 0, 0, :notes)
            """), {
                'class_id': row['class_id'], 'date': cleaned['date'].isoformat(),
                'start': cleaned['start'], 'end': cleaned['end'],
                'created_by': row['created_by'], 'ts': ts,
                'notes': f"Rescheduled by admin from {old_label}. Reason: {reason}",
            })
            new_id = insert.lastrowid
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Reschedule session error: {e}")
            return False, "Could not reschedule the session"

        self._log_admin_activity(
            admin_username, ActivityType.SESSION_DISMISSED,
            f"Admin rescheduled session {session_id} ({row['class_id']}) from "
            f"{old_label} to {new_label}; new session {new_id}. Reason: {reason}"
        )
        if notify:
            self._notify_lecturers(
                row['class_id'], f"Session moved: {row['class_id']}",
                f"The session on {old_label} was moved by the administrator to "
                f"{new_label}. Reason: {reason}", new_id
            )
        return True, f"{row['class_id']} moved from {old_label} to {new_label}", new_id

    # ==================================================================
    # Clashes
    # ==================================================================

    def find_conflicts(self, class_id, session_date, start_time, end_time, exclude_id=None):
        """
        Sessions that a session at this class/date/time would clash with.
        Returns [{'kind': 'class'|'lecturer'|'cohort', 'session_id', 'message'}].
        """
        cls = db.session.execute(text(
            "SELECT class_id, course_code, year FROM classes WHERE class_id = :c"
        ), {'c': class_id}).mappings().first()
        if not cls:
            return []

        lecturers = self._lecturers_by_class()
        mine = {l['instructor_id'] for l in lecturers.get(class_id, [])}

        occupying = ", ".join(f"'{s}'" for s in _OCCUPYING)
        others = db.session.execute(text(f"""
            SELECT s.session_id, s.class_id, s.start_time, s.end_time, s.status,
                   c.course_code, c.year
            FROM class_sessions s
            LEFT JOIN classes c ON c.class_id = s.class_id
            WHERE substr(s.date, 1, 10) = :d AND s.status IN ({occupying})
        """), {'d': session_date.isoformat()}).mappings().all()

        conflicts = []
        for o in others:
            if exclude_id and o['session_id'] == exclude_id:
                continue
            try:
                if not _times_overlap(start_time, end_time,
                                      _norm_time(o['start_time']), _norm_time(o['end_time'])):
                    continue
            except ValueError:
                continue

            slot = f"{_hm(o['start_time'])}-{_hm(o['end_time'])}"
            if o['class_id'] == class_id:
                conflicts.append({
                    'kind': 'class', 'session_id': o['session_id'],
                    'message': f"{class_id} already has a session at {slot} that day",
                })
                continue

            shared = mine & {l['instructor_id'] for l in lecturers.get(o['class_id'], [])}
            if shared:
                names = ', '.join(
                    l['instructor_name'] for l in lecturers.get(o['class_id'], [])
                    if l['instructor_id'] in shared
                )
                conflicts.append({
                    'kind': 'lecturer', 'session_id': o['session_id'],
                    'message': f"{names} teaches {o['class_id']} at {slot} that day",
                })
            if (o['course_code'], o['year']) == (cls['course_code'], cls['year']):
                conflicts.append({
                    'kind': 'cohort', 'session_id': o['session_id'],
                    'message': (f"{o['class_id']} is in the same cohort "
                                f"({cls['course_code']} year {cls['year']}) at {slot} that day"),
                })
        return conflicts

    # ==================================================================
    # Dismissals
    # ==================================================================

    def list_dismissals(self, status=None, instructor_id=None, page=1,
                        per_page=DEFAULT_PER_PAGE):
        """The lecturer dismissal log, newest first."""
        where, params = [], {}
        if status in DISMISSAL_STATUSES:
            where.append("d.status = :status")
            params['status'] = status
        if instructor_id:
            where.append("d.instructor_id = :iid")
            params['iid'] = instructor_id
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM session_dismissals d {clause}"
        ), params).scalar() or 0
        per_page = max(1, int(per_page))
        pages = max(1, -(-total // per_page))
        page = min(max(1, int(page)), pages)

        rows = db.session.execute(text(f"""
            SELECT d.id, d.session_id, d.instructor_id, i.instructor_name, d.reason,
                   d.dismissal_time, d.rescheduled_to, d.rescheduled_time, d.notes,
                   d.status, s.class_id, s.date, s.start_time, s.end_time,
                   s.status AS session_status
            FROM session_dismissals d
            LEFT JOIN instructors i ON i.instructor_id = d.instructor_id
            LEFT JOIN class_sessions s ON s.session_id = d.session_id
            {clause}
            ORDER BY d.dismissal_time DESC, d.id DESC
            LIMIT :limit OFFSET :offset
        """), dict(params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()

        items = []
        for r in rows:
            item = dict(r)
            item['date'] = _safe_date(r['date'])
            item['start_time'] = _hm(r['start_time'])
            item['end_time'] = _hm(r['end_time'])
            item['rescheduled_to'] = _safe_date(r['rescheduled_to'])
            items.append(item)

        return {'rows': items, 'total': total, 'page': page, 'pages': pages,
                'per_page': per_page}

    def dismissed_without_record(self):
        """Dismissed/cancelled sessions that have no dismissal row (older data)."""
        return db.session.execute(text("""
            SELECT COUNT(*) FROM class_sessions s
            WHERE s.status IN ('dismissed', 'cancelled')
              AND NOT EXISTS (SELECT 1 FROM session_dismissals d
                              WHERE d.session_id = s.session_id)
        """)).scalar() or 0

    def dismissal_instructors(self):
        """Lecturers that appear in the dismissal log (for its filter)."""
        rows = db.session.execute(text("""
            SELECT DISTINCT d.instructor_id, COALESCE(i.instructor_name, d.instructor_id) AS instructor_name
            FROM session_dismissals d
            LEFT JOIN instructors i ON i.instructor_id = d.instructor_id
            ORDER BY instructor_name
        """)).mappings().all()
        return [dict(r) for r in rows]

    # ==================================================================
    # Internals
    # ==================================================================

    def _get_row(self, session_id):
        """One session joined to its class and course, as a dict (or None)."""
        row = db.session.execute(text("""
            SELECT s.session_id, s.class_id, s.date, s.start_time, s.end_time,
                   s.status, s.created_by, s.created_at, s.updated_at,
                   s.attendance_count, s.total_students, s.session_notes,
                   c.class_name, c.course_code, c.year, c.semester,
                   c.is_active AS class_active, co.course_name
            FROM class_sessions s
            LEFT JOIN classes c ON c.class_id = s.class_id
            LEFT JOIN courses co ON co.course_code = c.course_code
            WHERE s.session_id = :id
        """), {'id': session_id}).mappings().first()
        return dict(row) if row else None

    def _modifiable(self, row):
        """(True, '') when the session can be cancelled or moved, else (False, why)."""
        if row['status'] != 'scheduled':
            label = STATUS_LABELS.get(row['status'], row['status'])
            return False, f"Only scheduled sessions can be changed: this one is {label.lower()}"

        touched = db.session.execute(text(f"""
            SELECT
              (SELECT COUNT(*) FROM attendance a WHERE a.session_id = :id) AS att,
              (SELECT COUNT(*) FROM session_dismissals d WHERE d.session_id = :id) AS dis,
              (SELECT COUNT(*) FROM system_metrics m WHERE m.session_id = :id) AS met
        """), {'id': row['session_id']}).mappings().first()
        if touched['att'] or touched['dis'] or touched['met']:
            return False, ("It already has attendance, a dismissal or metrics recorded, "
                           "so it counts as held")

        start_dt = _start_dt(row['date'], row['start_time'])
        if start_dt is None:
            return False, "The session's date or time can't be read"
        if start_dt <= _now():
            return False, "The session has already started or passed"
        return True, ""

    @staticmethod
    def _parse_move(new_date, start_time, end_time):
        """Validate the new slot. Returns (error, cleaned) - one of them is None."""
        try:
            d = _to_date(new_date)
            start, end = _norm_time(start_time), _norm_time(end_time)
        except (TypeError, ValueError):
            return "Enter a valid date and start and end times", None
        if d is None:
            return "Choose the new date", None
        if _minutes(end) <= _minutes(start):
            return "End time must be after start time", None
        return None, {'date': d, 'start': start, 'end': end}

    def _lecturers_by_class(self):
        """{class_id: [lecturers]}, earliest-assigned first."""
        return self._tt._lecturers_by_class()

    def _lecturers_for_class(self, class_id):
        return self._lecturers_by_class().get(class_id, [])

    def _notify_lecturers(self, class_id, title, message, session_id):
        """Tell the class's active lecturers. Never raises: it is a courtesy."""
        try:
            for lec in self._lecturers_for_class(class_id):
                if not lec['is_active']:
                    continue
                db.session.execute(text("""
                    INSERT INTO notifications
                        (user_id, user_type, title, message, type, is_read,
                         created_at, action_url, priority)
                    VALUES
                        (:uid, 'instructor', :title, :message, 'warning', 0,
                         :ts, :url, 'high')
                """), {'uid': lec['instructor_id'], 'title': title, 'message': message,
                       'ts': _ts(), 'url': f"/lecturer/sessions/{session_id}"})
            db.session.commit()
        except Exception as e:
            logger.error(f"Session notification error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    def _log_admin_activity(self, admin_username, activity_type, description):
        """Log an action under the admin's own identity (user_type='admin')."""
        try:
            db.session.execute(text("""
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (:user_id, :user_type, :activity_type, :description, :ts)
            """), {
                'user_id': admin_username, 'user_type': UserType.ADMIN,
                'activity_type': activity_type, 'description': description,
                'ts': _ts(),
            })
            db.session.commit()
        except Exception as e:
            logger.error(f"Admin activity logging error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass