"""
Attendance Admin Service (Phase 6b)
Campus-wide attendance oversight: held sessions with their numbers, per-class
and per-student summaries, a session sheet (every expected student, including
those with no attendance row) and admin corrections.

Design notes (match the live data, not the ORM):

- Plain ``text()`` SQL, like TimetableAdminService / SessionAdminService.

- ONE counting rule everywhere: a student "attended" when the status is
  Present or Late, and ``class_sessions.attendance_count`` is that number
  (SessionService._count_present_students does the same; verified on live data:
  every completed session's stored count equals its Present + Late rows).
  The rate is attended / records, so Excused stays in the denominator, exactly
  like the lecturer panel's ``calculate_session_statistics``.

- Who is "expected": active students with the same course and year_of_study as
  the class (the Phase 4 rule, ``Class.students``). A student who has an
  attendance row but is no longer in that group (deactivated, moved year) is
  still shown on the sheet, flagged "not in class now", so history never
  silently disappears.

- Only a ``completed`` session can be corrected. ``ongoing`` belongs to the live
  capture, ``scheduled`` / ``cancelled`` / ``dismissed`` / ``missed`` have
  nothing to correct (recording attendance for a missed session is a possible
  later feature, see the brief).

- A correction writes ``marked_by = NULL`` (that column is a foreign key to
  instructors and the admin is not one) and ``method = 'manual'``. Who, what and
  why live in ``attendance.notes`` (appended, never overwritten) and in the
  activity log, one row per student changed.

- The row changes and the session's ``attendance_count`` recompute are ONE
  transaction. Logging and notifying happen after the commit and never undo it.

- Each submitted row carries the status the admin SAW. If the row has changed
  since (a lecturer fixed it first), the whole batch is refused.

Methods that change data return (success, message[, extra]) tuples.
"""

from datetime import datetime
import logging
import re

from sqlalchemy import text

from app import db
from app.services.settings_admin_service import get_low_threshold
from app.services.timetable_admin_service import TimetableAdminService, _to_date
from config.constants import ActivityType, UserType

logger = logging.getLogger(__name__)

STATUSES = ('Present', 'Late', 'Absent', 'Excused')
STATUS_BADGES = {'Present': 'success', 'Late': 'warning', 'Absent': 'danger', 'Excused': 'info'}
ATTENDED = ('Present', 'Late')

# Sessions that have attendance to look at
HELD_STATUSES = ('completed', 'ongoing')
CORRECTABLE_STATUS = 'completed'

MAX_REASON = 300
MAX_BATCH = 500
DEFAULT_PER_PAGE = 50
NO_RECORD = 'No record'


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def _ts():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def _hm(value):
    return str(value)[:5] if value not in (None, '') else ''


def _safe_date(value):
    try:
        return _to_date(value)
    except ValueError:
        return None


_ADMIN_NOTE = re.compile(r'Corrected by admin (\S+?):')


def _append_note(existing, line):
    return f"{existing}\n{line}" if existing else line


def _rate(attended, records):
    """Percentage with one decimal, or None when there is nothing to divide by."""
    if not records:
        return None
    return round(attended * 100.0 / records, 1)


def _is_low(rate):
    return rate is not None and rate < get_low_threshold()


def _blank_counts():
    return {'Present': 0, 'Late': 0, 'Absent': 0, 'Excused': 0}


def _summarise(counts):
    """counts {'Present':..} -> adds records, attended, rate, low."""
    out = dict(counts)
    out['records'] = sum(counts[s] for s in STATUSES)
    out['attended'] = counts['Present'] + counts['Late']
    out['rate'] = _rate(out['attended'], out['records'])
    out['low'] = _is_low(out['rate'])
    return out


def _page(page, per_page, total):
    per_page = max(1, int(per_page))
    pages = max(1, -(-total // per_page))
    page = min(max(1, int(page)), pages)
    return page, pages, per_page


# SQL fragments that count one status over joined attendance rows `a`
_COUNT_COLS = ", ".join(
    f"COALESCE(SUM(CASE WHEN a.status = '{s}' THEN 1 ELSE 0 END), 0) AS n_{s.lower()}"
    for s in STATUSES
)


def _counts_from(row):
    return {s: row[f"n_{s.lower()}"] or 0 for s in STATUSES}


class AttendanceAdminService:
    """Admin attendance views and corrections."""

    def __init__(self):
        self._tt = TimetableAdminService()

    # ==================================================================
    # Reference data
    # ==================================================================

    def get_filter_options(self):
        """Active courses and lecturers for the filter dropdowns."""
        return self._tt.get_filter_options()

    # ==================================================================
    # Shared filters
    # ==================================================================

    @staticmethod
    def _session_filters(date_from, date_to, course_code, year, class_id, alias='s', class_alias='c'):
        where, params = [], {}
        if date_from:
            where.append(f"substr({alias}.date, 1, 10) >= :df")
            params['df'] = date_from.isoformat()
        if date_to:
            where.append(f"substr({alias}.date, 1, 10) <= :dt")
            params['dt'] = date_to.isoformat()
        if course_code:
            where.append(f"{class_alias}.course_code = :course")
            params['course'] = course_code
        if year:
            where.append(f"{class_alias}.year = :year")
            params['year'] = int(year)
        if class_id:
            where.append(f"{alias}.class_id LIKE :cid")
            params['cid'] = f"%{class_id}%"
        return where, params

    # ==================================================================
    # Held sessions (by session and by date range)
    # ==================================================================

    def list_held_sessions(self, date_from=None, date_to=None, course_code=None, year=None,
                           class_id=None, status=None, low_only=False, page=1,
                           per_page=DEFAULT_PER_PAGE):
        """
        Completed and ongoing sessions with their attendance numbers, newest
        first. ``status_counts`` ignores the status filter so the chips show how
        the rest of the filtered set splits. ``low_only`` keeps completed
        sessions whose stored rate is under the low-attendance setting.
        """
        where, params = self._session_filters(date_from, date_to, course_code, year, class_id)
        where.append("s.status IN ('completed', 'ongoing')")
        if low_only:
            where.append("s.status = 'completed' AND s.total_students > 0 "
                         "AND s.attendance_count * 100.0 / s.total_students < :thr")
            params['thr'] = get_low_threshold()
        base_where = "WHERE " + " AND ".join(where)

        count_rows = db.session.execute(text(
            "SELECT s.status AS status, COUNT(*) AS n FROM class_sessions s "
            "LEFT JOIN classes c ON c.class_id = s.class_id "
            f"{base_where} GROUP BY s.status"
        ), params).mappings().all()
        status_counts = {r['status']: r['n'] for r in count_rows}
        total_all = sum(status_counts.values())

        page_where, page_params = list(where), dict(params)
        if status in HELD_STATUSES:
            page_where.append("s.status = :status")
            page_params['status'] = status
            total = status_counts.get(status, 0)
        else:
            status = None
            total = total_all

        page, pages, per_page = _page(page, per_page, total)
        rows = db.session.execute(text(f"""
            SELECT s.session_id, s.class_id, s.date, s.start_time, s.end_time, s.status,
                   s.attendance_count, s.total_students, c.class_name, c.course_code, c.year
            FROM class_sessions s
            LEFT JOIN classes c ON c.class_id = s.class_id
            WHERE {" AND ".join(page_where)}
            ORDER BY substr(s.date, 1, 10) DESC, s.start_time DESC, s.class_id, s.session_id
            LIMIT :limit OFFSET :offset
        """), dict(page_params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()

        # Per-status counts for just this page's sessions
        by_session = {}
        ids = [r['session_id'] for r in rows]
        if ids:
            marks = ", ".join(f":i{n}" for n in range(len(ids)))
            att = db.session.execute(text(
                f"SELECT session_id, status, COUNT(*) AS n FROM attendance "
                f"WHERE session_id IN ({marks}) GROUP BY session_id, status"
            ), {f"i{n}": v for n, v in enumerate(ids)}).mappings().all()
            for a in att:
                by_session.setdefault(a['session_id'], _blank_counts())
                if a['status'] in by_session[a['session_id']]:
                    by_session[a['session_id']][a['status']] += a['n']

        items = []
        for r in rows:
            d = _safe_date(r['date'])
            counts = by_session.get(r['session_id'], _blank_counts())
            total_students = r['total_students'] or 0
            stored = r['attendance_count'] or 0
            rate = _rate(stored, total_students) if r['status'] == 'completed' else None
            items.append({
                'session_id': r['session_id'], 'class_id': r['class_id'],
                'class_name': r['class_name'] or '', 'course_code': r['course_code'] or '',
                'year': r['year'], 'date': d, 'date_raw': str(r['date'])[:10],
                'day_label': d.strftime('%a') if d else '',
                'start_time': _hm(r['start_time']), 'end_time': _hm(r['end_time']),
                'status': r['status'], 'attendance_count': stored,
                'total_students': total_students, 'counts': counts,
                'records': sum(counts.values()), 'rate': rate, 'low': _is_low(rate),
            })
        return {'rows': items, 'total': total, 'page': page, 'pages': pages,
                'per_page': per_page, 'status_counts': status_counts, 'total_all': total_all}

    # ==================================================================
    # By class
    # ==================================================================

    def class_summaries(self, date_from=None, date_to=None, course_code=None, year=None,
                        class_id=None, sort='class', low_only=False):
        """One row per class that has completed sessions in the range."""
        where, params = self._session_filters(date_from, date_to, course_code, year, class_id)
        where.append("s.status = 'completed'")
        rows = db.session.execute(text(f"""
            SELECT s.class_id, c.class_name, c.course_code, c.year,
                   COUNT(DISTINCT s.session_id) AS sessions, {_COUNT_COLS}
            FROM class_sessions s
            LEFT JOIN classes c ON c.class_id = s.class_id
            LEFT JOIN attendance a ON a.session_id = s.session_id
            WHERE {" AND ".join(where)}
            GROUP BY s.class_id
        """), params).mappings().all()

        items = []
        for r in rows:
            summary = _summarise(_counts_from(r))
            summary.update({
                'class_id': r['class_id'], 'class_name': r['class_name'] or '',
                'course_code': r['course_code'] or '', 'year': r['year'],
                'sessions': r['sessions'],
            })
            items.append(summary)
        if low_only:
            items = [i for i in items if i['low']]
        if sort == 'rate':
            items.sort(key=lambda i: (i['rate'] is None, i['rate'] or 0, i['class_id']))
        else:
            items.sort(key=lambda i: (i['course_code'], i['year'] or 0, i['class_id']))
        return items

    def get_class(self, class_id):
        row = db.session.execute(text("""
            SELECT c.class_id, c.class_name, c.course_code, c.year, c.semester,
                   c.is_active, co.course_name
            FROM classes c LEFT JOIN courses co ON co.course_code = c.course_code
            WHERE c.class_id = :id
        """), {'id': class_id}).mappings().first()
        return dict(row) if row else None

    def class_detail(self, class_id, date_from=None, date_to=None, sort='student'):
        """
        Per-student numbers for one class over its completed sessions: every
        student currently expected in the class, with zeros if they have no rows.
        """
        info = self.get_class(class_id)
        if not info:
            return None
        where, params = self._session_filters(date_from, date_to, None, None, None)
        where.append("s.class_id = :class_id")
        where.append("s.status = 'completed'")
        params['class_id'] = class_id

        held = db.session.execute(text(
            f"SELECT COUNT(*) FROM class_sessions s WHERE {' AND '.join(where)}"
        ), params).scalar() or 0

        rows = db.session.execute(text(f"""
            SELECT st.student_id, st.fname, st.lname, {_COUNT_COLS}
            FROM students st
            LEFT JOIN (
                SELECT a2.student_id, a2.status
                FROM attendance a2
                JOIN class_sessions s ON s.session_id = a2.session_id
                WHERE {" AND ".join(where)}
            ) a ON a.student_id = st.student_id
            WHERE st.is_active = 1 AND st.course = :course AND st.year_of_study = :year
            GROUP BY st.student_id
        """), dict(params, course=info['course_code'], year=info['year'])).mappings().all()

        students = []
        for r in rows:
            summary = _summarise(_counts_from(r))
            summary.update({'student_id': r['student_id'],
                            'name': f"{r['fname']} {r['lname']}".strip()})
            students.append(summary)
        if sort == 'rate':
            students.sort(key=lambda s: (s['rate'] is None, s['rate'] or 0, s['student_id']))
        else:
            students.sort(key=lambda s: s['student_id'])

        totals = _blank_counts()
        for s in students:
            for k in STATUSES:
                totals[k] += s[k]

        recent = db.session.execute(text("""
            SELECT session_id, date, start_time, end_time, status, attendance_count, total_students
            FROM class_sessions
            WHERE class_id = :cid AND status IN ('completed', 'ongoing')
            ORDER BY substr(date, 1, 10) DESC, start_time DESC LIMIT 15
        """), {'cid': class_id}).mappings().all()
        recent_sessions = []
        for r in recent:
            d = _safe_date(r['date'])
            tot = r['total_students'] or 0
            rate = _rate(r['attendance_count'] or 0, tot) if r['status'] == 'completed' else None
            recent_sessions.append({
                'session_id': r['session_id'], 'date': d, 'date_raw': str(r['date'])[:10],
                'start_time': _hm(r['start_time']), 'end_time': _hm(r['end_time']),
                'status': r['status'], 'attendance_count': r['attendance_count'] or 0,
                'total_students': tot, 'rate': rate, 'low': _is_low(rate),
            })
        return {'class': info, 'sessions_held': held, 'students': students,
                'totals': _summarise(totals), 'recent_sessions': recent_sessions}

    # ==================================================================
    # By student
    # ==================================================================

    def list_students(self, query=None, course_code=None, year=None, low_only=False,
                      page=1, per_page=DEFAULT_PER_PAGE):
        """Students with their overall attendance (completed sessions only)."""
        where, params = [], {}
        if query:
            where.append("(st.student_id LIKE :q OR st.fname LIKE :q OR st.lname LIKE :q "
                         "OR (st.fname || ' ' || st.lname) LIKE :q)")
            params['q'] = f"%{query}%"
        if course_code:
            where.append("st.course = :course")
            params['course'] = course_code
        if year:
            where.append("st.year_of_study = :year")
            params['year'] = int(year)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        if low_only:
            # Needs every student's rate before it can filter, so aggregate them all
            params['thr'] = get_low_threshold()
            base = f"""
                FROM students st
                LEFT JOIN attendance a ON a.student_id = st.student_id
                    AND a.session_id IN (SELECT session_id FROM class_sessions WHERE status = 'completed')
                {where_sql}
                GROUP BY st.student_id
                HAVING COUNT(a.status) > 0 AND
                       SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) * 100.0
                       / COUNT(a.status) < :thr
            """
            total = db.session.execute(text(
                f"SELECT COUNT(*) FROM (SELECT st.student_id {base})"), params).scalar() or 0
            page, pages, per_page = _page(page, per_page, total)
            rows = db.session.execute(text(f"""
                SELECT st.student_id, st.fname, st.lname, st.course, st.year_of_study,
                       st.is_active, {_COUNT_COLS}
                {base}
                ORDER BY st.student_id LIMIT :limit OFFSET :offset
            """), dict(params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()
        else:
            # Page the students first, then count attendance for just that page
            total = db.session.execute(text(
                f"SELECT COUNT(*) FROM students st {where_sql}"), params).scalar() or 0
            page, pages, per_page = _page(page, per_page, total)
            rows = db.session.execute(text(f"""
                SELECT st.student_id, st.fname, st.lname, st.course, st.year_of_study,
                       st.is_active, {_COUNT_COLS}
                FROM (SELECT * FROM students st {where_sql}
                      ORDER BY st.student_id LIMIT :limit OFFSET :offset) st
                LEFT JOIN attendance a ON a.student_id = st.student_id
                    AND a.session_id IN (SELECT session_id FROM class_sessions WHERE status = 'completed')
                GROUP BY st.student_id
                ORDER BY st.student_id
            """), dict(params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()

        items = []
        for r in rows:
            summary = _summarise(_counts_from(r))
            summary.update({
                'student_id': r['student_id'], 'name': f"{r['fname']} {r['lname']}".strip(),
                'course': r['course'] or '', 'year': r['year_of_study'],
                'is_active': bool(r['is_active']),
            })
            items.append(summary)
        return {'rows': items, 'total': total, 'page': page, 'pages': pages, 'per_page': per_page}

    def get_student(self, student_id, date_from=None, date_to=None, page=1,
                    per_page=DEFAULT_PER_PAGE):
        """A student's totals, per-class totals and session-by-session history."""
        st = db.session.execute(text("""
            SELECT student_id, fname, lname, email, course, year_of_study, is_active
            FROM students WHERE student_id = :id
        """), {'id': student_id}).mappings().first()
        if not st:
            return None

        where, params = self._session_filters(date_from, date_to, None, None, None)
        where.append("s.status IN ('completed', 'ongoing')")
        where.append("a.student_id = :sid")
        params['sid'] = student_id
        base = (
            "FROM attendance a JOIN class_sessions s ON s.session_id = a.session_id "
            "LEFT JOIN classes c ON c.class_id = s.class_id "
            f"WHERE {' AND '.join(where)}"
        )

        totals_row = db.session.execute(text(
            f"SELECT {_COUNT_COLS} {base} AND s.status = 'completed'"), params).mappings().first()
        totals = _summarise(_counts_from(totals_row))

        per_class_rows = db.session.execute(text(f"""
            SELECT s.class_id, c.class_name, {_COUNT_COLS}
            {base} AND s.status = 'completed'
            GROUP BY s.class_id ORDER BY s.class_id
        """), params).mappings().all()
        per_class = []
        for r in per_class_rows:
            summary = _summarise(_counts_from(r))
            summary.update({'class_id': r['class_id'], 'class_name': r['class_name'] or ''})
            per_class.append(summary)

        total_rows = db.session.execute(text(f"SELECT COUNT(*) {base}"), params).scalar() or 0
        page, pages, per_page = _page(page, per_page, total_rows)
        history_rows = db.session.execute(text(f"""
            SELECT a.id, a.status AS att_status, a.method, a.confidence_score, a.notes,
                   s.session_id, s.class_id, s.date, s.start_time, s.end_time,
                   s.status AS session_status, c.class_name
            {base}
            ORDER BY substr(s.date, 1, 10) DESC, s.start_time DESC, s.session_id DESC
            LIMIT :limit OFFSET :offset
        """), dict(params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()
        history = []
        for r in history_rows:
            d = _safe_date(r['date'])
            history.append({
                'session_id': r['session_id'], 'class_id': r['class_id'],
                'class_name': r['class_name'] or '', 'date': d, 'date_raw': str(r['date'])[:10],
                'start_time': _hm(r['start_time']), 'end_time': _hm(r['end_time']),
                'session_status': r['session_status'], 'status': r['att_status'],
                'method': r['method'] or '', 'confidence': r['confidence_score'],
                'corrected': bool(r['notes'] and 'Corrected by admin' in r['notes']),
            })
        return {
            'student': {'student_id': st['student_id'],
                        'name': f"{st['fname']} {st['lname']}".strip(), 'email': st['email'],
                        'course': st['course'] or '', 'year': st['year_of_study'],
                        'is_active': bool(st['is_active'])},
            'totals': totals, 'per_class': per_class, 'history': history,
            'page': page, 'pages': pages, 'per_page': per_page, 'total_rows': total_rows,
        }

    # ==================================================================
    # Session sheet
    # ==================================================================

    def _get_session_row(self, session_id):
        row = db.session.execute(text("""
            SELECT s.session_id, s.class_id, s.date, s.start_time, s.end_time, s.status,
                   s.attendance_count, s.total_students, s.session_notes,
                   c.class_name, c.course_code, c.year, c.semester, co.course_name
            FROM class_sessions s
            LEFT JOIN classes c ON c.class_id = s.class_id
            LEFT JOIN courses co ON co.course_code = c.course_code
            WHERE s.session_id = :id
        """), {'id': session_id}).mappings().first()
        return dict(row) if row else None

    def _expected_students(self, course_code, year):
        rows = db.session.execute(text("""
            SELECT student_id, fname, lname FROM students
            WHERE is_active = 1 AND course = :course AND year_of_study = :year
            ORDER BY student_id
        """), {'course': course_code, 'year': year}).mappings().all()
        return {r['student_id']: f"{r['fname']} {r['lname']}".strip() for r in rows}

    def get_sheet(self, session_id):
        """
        The session sheet: one entry per expected student plus anyone who has a
        row, with the session summary and whether it can be corrected.
        """
        row = self._get_session_row(session_id)
        if not row:
            return None

        expected = self._expected_students(row['course_code'], row['year']) \
            if row['course_code'] and row['year'] else {}
        records = db.session.execute(text("""
            SELECT a.id, a.student_id, a.status, a.method, a.confidence_score, a.timestamp,
                   a.marked_by, a.notes, i.instructor_name,
                   st.fname, st.lname, st.is_active
            FROM attendance a
            LEFT JOIN instructors i ON i.instructor_id = a.marked_by
            LEFT JOIN students st ON st.student_id = a.student_id
            WHERE a.session_id = :id
        """), {'id': session_id}).mappings().all()
        by_student = {r['student_id']: r for r in records}

        entries = []
        for sid in sorted(set(expected) | set(by_student)):
            r = by_student.get(sid)
            if sid in expected:
                name = expected[sid]
            elif r is not None:
                name = f"{r['fname'] or ''} {r['lname'] or ''}".strip() or sid
            else:
                name = sid
            marked_by = None
            if r is not None:
                marked_by = r['instructor_name'] or r['marked_by']
                if not marked_by:
                    # marked_by is NULL for admin corrections; the note says who
                    m = _ADMIN_NOTE.findall(r['notes'] or '')
                    marked_by = f"admin {m[-1]}" if m else ''
            entries.append({
                'student_id': sid, 'name': name,
                'in_class': sid in expected,
                'inactive': bool(r is not None and sid not in expected and r['is_active'] == 0),
                'has_row': r is not None,
                'status': r['status'] if r is not None else None,
                'method': (r['method'] or '') if r is not None else '',
                'confidence': r['confidence_score'] if r is not None else None,
                'timestamp': str(r['timestamp'])[:16] if r is not None and r['timestamp'] else '',
                'marked_by': marked_by or '',
                'corrected': bool(r is not None and r['notes'] and 'Corrected by admin' in r['notes']),
                'last_note': self._last_note_line(r['notes']) if r is not None else '',
            })

        counts = _blank_counts()
        no_record = 0
        for e in entries:
            if e['status'] in counts:
                counts[e['status']] += 1
            else:
                no_record += 1
        attended = counts['Present'] + counts['Late']
        expected_n = len(entries)
        stored = row['attendance_count'] or 0
        can, why = self._correctable(row)
        d = _safe_date(row['date'])
        rate = _rate(attended, expected_n)
        return {
            'session': {
                'session_id': row['session_id'], 'class_id': row['class_id'],
                'class_name': row['class_name'] or '', 'course_code': row['course_code'] or '',
                'course_name': row['course_name'] or '', 'year': row['year'],
                'semester': row['semester'], 'date': d, 'date_raw': str(row['date'])[:10],
                'day_name': d.strftime('%A') if d else '',
                'start_time': _hm(row['start_time']), 'end_time': _hm(row['end_time']),
                'status': row['status'], 'attendance_count': stored,
                'total_students': row['total_students'] or 0,
            },
            'entries': entries,
            'summary': dict(counts, no_record=no_record, expected=expected_n,
                            attended=attended, rate=rate, low=_is_low(rate)),
            'count_mismatch': stored != attended and row['status'] == 'completed',
            'can_correct': can, 'cannot_correct_reason': None if can else why,
        }

    @staticmethod
    def _last_note_line(notes):
        if not notes:
            return ''
        lines = [ln for ln in str(notes).splitlines() if ln.strip()]
        return lines[-1] if lines else ''

    @staticmethod
    def _correctable(row):
        if row['status'] == CORRECTABLE_STATUS:
            return True, None
        reasons = {
            'ongoing': "A lecturer is running this session; wait until it has been ended",
            'scheduled': "This session has not been held yet",
            'cancelled': "This session was cancelled, so there is no attendance to correct",
            'dismissed': "This session was dismissed by the lecturer, so there is no attendance to correct",
            'missed': "This session was missed, so there is no attendance to correct",
        }
        return False, reasons.get(row['status'], "Only completed sessions can be corrected")

    # ==================================================================
    # Corrections
    # ==================================================================

    def correct(self, admin_username, session_id, items, new_status, reason, notify=True):
        """
        Set ``new_status`` on several students of one completed session.

        ``items`` is a list of ``(student_id, seen_status)`` where ``seen_status``
        is what the admin saw ('' or None for "no record"). Returns
        ``(success, message, extra)``; nothing is written unless everything checks out.
        """
        reason = (reason or '').strip()
        if new_status not in STATUSES:
            return False, "Choose a status to apply", None
        if not reason:
            return False, "Give a reason for the correction", None
        if len(reason) > MAX_REASON:
            return False, f"Keep the reason under {MAX_REASON} characters", None

        seen = {}
        for sid, seen_status in items or []:
            sid = (sid or '').strip()
            if sid:
                seen[sid] = (seen_status or '').strip() or None
        if not seen:
            return False, "Select at least one student", None
        if len(seen) > MAX_BATCH:
            return False, f"Correct at most {MAX_BATCH} students at a time", None

        row = self._get_session_row(session_id)
        if not row:
            return False, "Session not found", None
        ok, why = self._correctable(row)
        if not ok:
            return False, why, None

        expected = self._expected_students(row['course_code'], row['year'])
        label = f"{row['class_id']} on {self._nice(row)}"
        ts = _ts()
        changed, skipped = [], 0
        try:
            existing = {}
            marks = ", ".join(f":s{n}" for n in range(len(seen)))
            for r in db.session.execute(text(
                f"SELECT id, student_id, status, method, confidence_score, notes "
                f"FROM attendance WHERE session_id = :sid AND student_id IN ({marks})"
            ), dict({f"s{n}": v for n, v in enumerate(seen)}, sid=session_id)).mappings().all():
                existing[r['student_id']] = r

            # Validate everything first, so a refusal writes nothing
            stale, outsiders = [], []
            for sid, seen_status in seen.items():
                current = existing[sid]['status'] if sid in existing else None
                if current != seen_status:
                    stale.append(sid)
                if sid not in existing and sid not in expected:
                    outsiders.append(sid)
            if outsiders:
                return False, (f"{outsiders[0]} is not in this class and has no record in "
                               f"this session, so it cannot be added"), None
            if stale:
                return False, (f"{len(stale)} record(s) changed since you opened the sheet "
                               f"(for example {stale[0]}). Reload the sheet and check them again"), None

            for sid in seen:
                row_now = existing.get(sid)
                old = row_now['status'] if row_now else None
                if old == new_status:
                    skipped += 1
                    continue
                old_label = old or NO_RECORD
                line = (f"[{ts[:10]}] Corrected by admin {admin_username}: "
                        f"{old_label} -> {new_status}. Reason: {reason}")
                if row_now:
                    extra = []
                    if row_now['method'] and row_now['method'] != 'manual':
                        extra.append(f"was marked by {row_now['method']}")
                    if new_status in ('Absent', 'Excused') and row_now['confidence_score'] is not None:
                        extra.append(f"face match {row_now['confidence_score']:.2f} cleared")
                    if extra:
                        line += " (" + "; ".join(extra) + ")"
                    clear_conf = new_status in ('Absent', 'Excused')
                    result = db.session.execute(text("""
                        UPDATE attendance
                        SET status = :new, marked_by = NULL, method = 'manual', timestamp = :ts,
                            confidence_score = CASE WHEN :clear = 1 THEN NULL ELSE confidence_score END,
                            notes = :notes
                        WHERE id = :id AND status = :old
                    """), {'new': new_status, 'ts': ts, 'clear': 1 if clear_conf else 0,
                           'notes': _append_note(row_now['notes'], line),
                           'id': row_now['id'], 'old': old})
                    if result.rowcount != 1:
                        db.session.rollback()
                        return False, ("A record changed while you were working. "
                                       "Reload the sheet and try again"), None
                else:
                    db.session.execute(text("""
                        INSERT INTO attendance
                            (student_id, session_id, timestamp, status, marked_by, method,
                             confidence_score, notes)
                        VALUES (:sid, :session, :ts, :new, NULL, 'manual', NULL, :notes)
                    """), {'sid': sid, 'session': session_id, 'ts': ts,
                           'new': new_status, 'notes': line})
                changed.append((sid, old_label))

            if not changed:
                db.session.rollback()
                return False, f"Nothing to change: all selected students are already {new_status}", None

            # Recompute the session's numbers in the same transaction
            db.session.execute(text("""
                UPDATE class_sessions
                SET attendance_count = (SELECT COUNT(*) FROM attendance
                                        WHERE session_id = :id AND status IN ('Present', 'Late')),
                    total_students = CASE WHEN COALESCE(total_students, 0) = 0
                                          THEN :expected ELSE total_students END,
                    updated_at = :ts
                WHERE session_id = :id
            """), {'id': session_id, 'ts': ts, 'expected': self._sheet_size(session_id, expected)})
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Attendance correction error: {e}")
            return False, "Could not save the correction", None

        count_row = self._get_session_row(session_id)
        count = count_row['attendance_count'] or 0
        total = count_row['total_students'] or 0

        for sid, old_label in changed:
            self._log_admin_activity(
                admin_username, ActivityType.ATTENDANCE_CORRECTED,
                f"Admin corrected {sid} in session {session_id} ({label}): "
                f"{old_label} -> {new_status}. Reason: {reason}"
            )
        if notify:
            self._notify_lecturers(
                row['class_id'], f"Attendance corrected: {row['class_id']}",
                f"An administrator corrected {len(changed)} attendance record(s) for the "
                f"session on {self._nice(row)}, set to {new_status}. Reason: {reason}",
                session_id)

        msg = f"Set {len(changed)} student{'' if len(changed) == 1 else 's'} to {new_status}"
        if skipped:
            msg += f" ({skipped} already {new_status})"
        msg += f". Session count is now {count}/{total}"
        return True, msg, {'changed': len(changed), 'skipped': skipped,
                           'attendance_count': count, 'total_students': total}

    @staticmethod
    def _sheet_size(session_id, expected):
        """Students on the sheet: everyone expected plus anyone with a row."""
        rows = db.session.execute(text(
            "SELECT student_id FROM attendance WHERE session_id = :id"), {'id': session_id}).fetchall()
        return len(set(expected) | {r[0] for r in rows})

    @staticmethod
    def _nice(row):
        d = _safe_date(row['date'])
        when = d.strftime('%a %d %b %Y') if d else str(row['date'])[:10]
        return f"{when} {_hm(row['start_time'])}"

    # ==================================================================
    # Corrections log
    # ==================================================================

    def list_corrections(self, who='admin', query=None, page=1, per_page=DEFAULT_PER_PAGE):
        """Attendance corrections from the activity log (admin only, or everyone)."""
        where = ["activity_type = :atype"]
        params = {'atype': ActivityType.ATTENDANCE_CORRECTED}
        if who != 'all':
            where.append("user_type = :utype")
            params['utype'] = UserType.ADMIN
        if query:
            where.append("description LIKE :q")
            params['q'] = f"%{query}%"
        where_sql = " AND ".join(where)
        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM activity_log WHERE {where_sql}"), params).scalar() or 0
        page, pages, per_page = _page(page, per_page, total)
        rows = db.session.execute(text(f"""
            SELECT user_id, user_type, description, timestamp
            FROM activity_log WHERE {where_sql}
            ORDER BY timestamp DESC, rowid DESC LIMIT :limit OFFSET :offset
        """), dict(params, limit=per_page, offset=(page - 1) * per_page)).mappings().all()
        return {'rows': [dict(r) for r in rows], 'total': total, 'page': page,
                'pages': pages, 'per_page': per_page}

    # ==================================================================
    # Side effects (never undo a committed correction)
    # ==================================================================

    def _notify_lecturers(self, class_id, title, message, session_id):
        try:
            for lec in self._tt._lecturers_by_class().get(class_id, []):
                if not lec['is_active']:
                    continue
                db.session.execute(text("""
                    INSERT INTO notifications
                        (user_id, user_type, title, message, type, is_read,
                         created_at, action_url, priority)
                    VALUES
                        (:uid, 'instructor', :title, :message, 'info', 0,
                         :ts, :url, 'normal')
                """), {'uid': lec['instructor_id'], 'title': title, 'message': message,
                       'ts': _ts(), 'url': f"/lecturer/sessions/{session_id}"})
            db.session.commit()
        except Exception as e:
            logger.error(f"Correction notification error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    def _log_admin_activity(self, admin_username, activity_type, description):
        try:
            db.session.execute(text("""
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (:user_id, :user_type, :activity_type, :description, :ts)
            """), {'user_id': admin_username, 'user_type': UserType.ADMIN,
                   'activity_type': activity_type, 'description': description, 'ts': _ts()})
            db.session.commit()
        except Exception as e:
            logger.error(f"Admin activity logging error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass