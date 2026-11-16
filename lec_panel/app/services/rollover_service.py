"""
Semester Rollover Service (Phase 7c)

What a rollover does, when the campus semester has changed since the last one:

  Semester 1 -> 2 (January)   create semester-2 ``student_courses`` rows for active
                              students, mark the semester-1 rows Completed, roll the
                              timetable's effective dates to the new window, record the
                              new semester in ``students.current_semester``.
  Semester 2 -> 1 (autumn)    mark the semester-2 rows Completed, roll the timetable,
                              record the semester. It creates NO enrolment rows: the new
                              academic year changes ``year_of_study`` first (the yearly
                              promotion, Phase 7d), which then creates the rows, so no row
                              is ever written with a stale year.

Design notes (match the live data, not the ORM):

- "Due" is decided by a stored marker (``marker_rollover`` = ``<academic year>:<semester>``,
  see ``app/utils/markers.py``) compared with what the 7b readers say today. Before the
  first rollover there is no marker: the term the Active enrolment rows are in is taken as
  the baseline, so nothing is "due" while the data already matches the campus.
  A calendar edit that moves the campus BACK to an earlier term than the marker never
  reverses anything: the page warns and nothing is offered.
- Checking is a cheap read made whenever the dashboard or settings page loads. Nothing
  runs by itself: the admin previews and clicks "Run now" (admin-run, not a silent job).
- ``plan`` reads only. ``run`` re-plans, refuses if the plan no longer matches the one the
  admin previewed (fingerprint), writes a verified backup, and then does everything in ONE
  transaction that starts with a compare-and-swap of the marker. The activity log row is
  written after the commit and never undoes it.
- Rows are acted on by ``id``. Only ``Active`` rows of the finished semester become
  Completed; ``Dropped`` / ``Failed`` / ``Completed`` rows are never touched, and rows with
  a NULL semester are left alone (counted in the preview).
- Plain ``text()`` SQL throughout: the live tables hold text dates and integer semesters
  while the ORM declares other types.
- The timetable roll uses the same rule as the Generate page's "Roll forward expired
  entries" (active entries of active classes of the semester whose ``effective_to`` ends
  before the window's end move to the window). Rollover moves dates only: it generates no
  sessions (the Generate page still does that).
"""

import csv
import hashlib
import io
import json
import logging
from datetime import date, datetime

from flask import g, has_app_context
from sqlalchemy import text

from app import db
from app.utils import academic_calendar as calendar
from app.utils import calendar_rules as rules
from app.utils.db_backup import BackupError, backup_database, default_backup_dir
from app.utils.markers import format_term, parse_term, read_marker_info, swap_marker
from config.constants import ActivityType, EnrollmentStatus, UserType

logger = logging.getLogger(__name__)

MARKER = 'rollover'
MAX_SKIPPED_SHOWN = 50

KIND_LABELS = {
    'to_sem2': 'Semester 1 to semester 2',
    'to_sem1': 'Semester 2 to semester 1 (new academic year)',
}

SKIP_REASONS = {
    'no_course': "The student has no course",
    'course_missing': "The student's course is not in the course list",
    'no_year': "The student has no year of study",
    'already_present': "A row for this semester already exists",
    'dropped': "Dropped the course last semester (not re-enrolled automatically)",
}


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def term_label(academic_year, semester):
    return f"{rules.year_label(academic_year)} semester {semester}"


def _kind(finished_semester, target_semester):
    if finished_semester == 1 and target_semester == 2:
        return 'to_sem2'
    if finished_semester == 2 and target_semester == 1:
        return 'to_sem1'
    return None


def _scalar(sql, params=None):
    return db.session.execute(text(sql), params or {}).scalar()


def _db_path():
    return db.engine.url.database


def _safe_cell(value):
    """Spreadsheet-injection defence, same rule as the 6c exports."""
    s = '' if value is None else str(value)
    return "'" + s if s[:1] in ('=', '+', '-', '@', '\t', '\r') else s


# ----------------------------------------------------------------------
# State: is a rollover due?  (call time, memoised per request, never raises)
# ----------------------------------------------------------------------

def compute_state(today=None):
    """
    ``{'target', 'target_label', 'last', 'marker_raw', 'baseline', 'finished_semester',
    'kind', 'due', 'blocked', 'reversed', 'level', 'message'}``. ``target`` and ``last``
    are ``(academic_year, semester)``. Reads only.
    """
    ay = calendar.get_academic_year(today)
    sem = calendar.get_current_semester(today)
    target = (ay, sem)
    info = read_marker_info(MARKER)
    raw = info['value'] if info else None
    last = parse_term(raw) if raw else None

    state = {'target': target, 'target_label': term_label(ay, sem), 'last': last,
             'marker_raw': raw, 'baseline': False, 'finished_semester': None,
             'kind': None, 'due': False, 'blocked': False, 'reversed': False,
             'level': 'success', 'message': ''}

    if raw is not None and (last is None or last[1] not in (1, 2)):
        state.update(blocked=True, level='danger', message=(
            "The stored rollover marker is unreadable, so no rollover is offered. "
            "It needs a look before anything is run."))
        return state

    if last is not None:
        last_label = term_label(*last)
        if last == target:
            state['message'] = f"Enrolments are set up for {state['target_label']}. Nothing to roll over."
            return state
        if last > target:
            state.update(reversed=True, level='warning', message=(
                f"A rollover was already run for {last_label}, but the calendar now places today in "
                f"{state['target_label']}. Nothing is reversed and nothing is offered. "
                f"Check the calendar dates on the settings page."))
            return state
        fin = last[1]
        origin = f"the last rollover was for {last_label}"
    else:
        state['baseline'] = True
        rows = db.session.execute(text(
            "SELECT semester, COUNT(*) AS n FROM student_courses "
            "WHERE status = 'Active' AND semester IN (1, 2) "
            "GROUP BY semester ORDER BY n DESC, semester")).all()
        if not rows:
            state['message'] = ("No rollover has been recorded and there are no active enrolment rows, "
                                "so there is nothing to roll over.")
            return state
        fin = int(rows[0][0])
        if fin == sem:
            state['message'] = (
                f"No rollover has been recorded yet. The active enrolments are already for semester {sem}, "
                f"which matches the campus ({state['target_label']}), so nothing is due. "
                f"The first rollover will record its marker.")
            return state
        origin = f"the active enrolments are still for semester {fin}"

    kind = _kind(fin, sem)
    state['finished_semester'] = fin
    if kind is None:
        state.update(blocked=True, level='danger', message=(
            f"The campus is now in {state['target_label']} but {origin}. That skips at least one "
            f"semester, so it cannot be rolled over automatically. Check the calendar dates; "
            f"do not edit enrolment rows by hand before that is sorted out."))
        return state

    state.update(kind=kind, due=True, level='warning', message=(
        f"Rollover due: the campus is now in {state['target_label']} but {origin}."))
    return state


def _memo_get():
    if has_app_context():
        return getattr(g, '_rollover_state_memo', None)
    return None


def clear_rollover_memo():
    if has_app_context() and hasattr(g, '_rollover_state_memo'):
        g._rollover_state_memo = None


def get_rollover_state():
    """Reader for the dashboard and settings page. Memoised per request, never raises."""
    memo = _memo_get()
    if memo is not None:
        return memo
    try:
        state = compute_state()
    except Exception as e:
        logger.error(f"Could not check whether a rollover is due: {e}")
        return {'due': False, 'blocked': False, 'reversed': False, 'error': True,
                'level': 'secondary', 'message': "Could not check whether a rollover is due."}
    if has_app_context():
        g._rollover_state_memo = state
    return state


# ----------------------------------------------------------------------
# Plan (reads only; also the preview)
# ----------------------------------------------------------------------

def build_plan(state):
    """What a rollover would do for a due ``state``. Writes nothing."""
    tgt_ay, tgt_sem = state['target']
    fin = state['finished_semester']
    kind = state['kind']
    window = calendar.get_year_windows(tgt_ay)[tgt_sem]

    # Finished-semester rows still Active -> Completed (by id)
    complete = db.session.execute(text(
        "SELECT id FROM student_courses WHERE status = 'Active' AND semester = :fin ORDER BY id"),
        {'fin': fin}).all()
    complete_ids = [int(r[0]) for r in complete]
    null_semester_active = _scalar(
        "SELECT COUNT(*) FROM student_courses WHERE status = 'Active' AND semester IS NULL") or 0

    # New rows (semester 1 -> 2 only)
    creates, skipped = [], []
    if kind == 'to_sem2':
        courses = {r[0] for r in db.session.execute(text("SELECT course_code FROM courses")).all()}
        present = {(r[0], r[1], r[2]) for r in db.session.execute(text(
            "SELECT student_id, course_code, year FROM student_courses WHERE semester = :t"),
            {'t': tgt_sem}).all()}
        last_term = {}
        for sid, cc, st in db.session.execute(text(
                "SELECT student_id, course_code, status FROM student_courses WHERE semester = :f"),
                {'f': fin}).all():
            last_term.setdefault((sid, cc), set()).add(st)

        students = db.session.execute(text(
            "SELECT student_id, course, year_of_study FROM students "
            "WHERE is_active = 1 ORDER BY student_id")).all()
        for sid, course, year in students:
            code = (course or '').strip()
            reason = None
            if not code:
                reason = 'no_course'
            elif code not in courses:
                reason = 'course_missing'
            elif year is None or int(year) < 1:
                reason = 'no_year'
            elif (sid, code, int(year)) in present:
                reason = 'already_present'
            else:
                seen = last_term.get((sid, code), set())
                if 'Dropped' in seen and not (seen & {'Active', 'Completed'}):
                    reason = 'dropped'
            if reason:
                skipped.append({'student_id': sid, 'course_code': code, 'year': year,
                                'reason': reason, 'reason_text': SKIP_REASONS[reason]})
            else:
                creates.append({'student_id': sid, 'course_code': code, 'year': int(year)})

    # Timetable entries to roll (same rule as the Generate page's roll-forward)
    start, end = window
    tt = db.session.execute(text("""
        SELECT t.id FROM timetable t
        JOIN classes c ON c.class_id = t.class_id
        WHERE t.is_active = 1 AND c.is_active = 1 AND c.semester = :sem
          AND t.effective_to IS NOT NULL AND t.effective_to < :end
        ORDER BY t.id
    """), {'sem': tgt_sem, 'end': end.isoformat()}).all()
    timetable_ids = [int(r[0]) for r in tt]

    # students.current_semester follows the campus (active students only)
    stu = db.session.execute(text(
        "SELECT student_id FROM students WHERE is_active = 1 "
        "AND (current_semester IS NULL OR current_semester != :s) ORDER BY student_id"),
        {'s': tgt_sem}).all()
    student_ids = [r[0] for r in stu]

    by_reason = {}
    for s in skipped:
        by_reason[s['reason']] = by_reason.get(s['reason'], 0) + 1

    payload = json.dumps({
        't': list(state['target']), 'f': fin, 'last': state['marker_raw'],
        'c': [[c['student_id'], c['course_code'], c['year']] for c in creates],
        'x': complete_ids, 'tt': timetable_ids, 's': student_ids,
    }, sort_keys=True)

    return {
        'target': state['target'], 'target_label': state['target_label'],
        'finished_semester': fin, 'kind': kind, 'kind_label': KIND_LABELS[kind],
        'creates': creates, 'skipped': skipped, 'complete_ids': complete_ids,
        'timetable_ids': timetable_ids, 'window': window, 'student_ids': student_ids,
        'counts': {
            'create': len(creates), 'complete': len(complete_ids),
            'timetable': len(timetable_ids), 'students': len(student_ids),
            'skipped': len(skipped), 'skipped_by_reason': by_reason,
            'null_semester_active': int(null_semester_active),
            'inactive_students': int(_scalar(
                "SELECT COUNT(*) FROM students WHERE is_active = 0 OR is_active IS NULL") or 0),
        },
        'fingerprint': hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16],
    }


def skipped_csv(plan):
    """UTF-8 (with BOM, for Excel) CSV of the students who get no new row, and why."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\r\n')
    writer.writerow(['student_id', 'course', 'year_of_study', 'reason'])
    for s in plan['skipped']:
        writer.writerow([_safe_cell(s['student_id']), _safe_cell(s['course_code']),
                         _safe_cell(s['year']), _safe_cell(s['reason_text'])])
    return ('\ufeff' + buf.getvalue()).encode('utf-8')


# ----------------------------------------------------------------------
# Service used by the page
# ----------------------------------------------------------------------

class RolloverService:

    def page(self, today=None):
        """Everything the rollover page needs."""
        state = compute_state(today)
        plan = build_plan(state) if state['due'] else None
        info = read_marker_info(MARKER)
        try:
            backup_dir = str(default_backup_dir(_db_path()))
        except Exception:
            backup_dir = ''
        return {
            'state': state, 'plan': plan,
            'skipped_shown': plan['skipped'][:MAX_SKIPPED_SHOWN] if plan else [],
            'marker': info, 'recent': self.recent_runs(), 'backup_dir': backup_dir,
            'max_skipped_shown': MAX_SKIPPED_SHOWN,
        }

    def skipped_csv(self, today=None):
        """(bytes, filename) or None when no rollover is due."""
        state = compute_state(today)
        if not state['due']:
            return None
        plan = build_plan(state)
        name = f"rollover_skipped_{(today or date.today()).strftime('%Y%m%d')}.csv"
        return skipped_csv(plan), name

    @staticmethod
    def recent_runs(limit=5):
        try:
            rows = db.session.execute(text(
                "SELECT user_id, description, timestamp FROM activity_log "
                "WHERE activity_type = :t ORDER BY id DESC LIMIT :n"),
                {'t': _activity_type(), 'n': limit}).all()
            return [{'user': r[0], 'description': r[1], 'timestamp': str(r[2] or '')[:16]}
                    for r in rows]
        except Exception as e:
            logger.error(f"Could not list recent rollovers: {e}")
            return []

    # ------------------------------------------------------------------

    def run(self, admin_username, fingerprint, today=None):
        """
        Run the rollover the admin previewed. Returns ``(success, message, result)``.

        Order: check due -> check the preview is still current -> backup (a failed
        backup stops everything) -> ONE transaction: compare-and-swap the marker,
        re-plan, compare again, write -> commit -> log. Any failure rolls back.
        """
        state = compute_state(today)
        if not state['due']:
            return False, state['message'] or "No rollover is due.", None

        plan = build_plan(state)
        if not fingerprint or fingerprint != plan['fingerprint']:
            return (False, "The data changed since the preview was made. Nothing was changed; "
                           "review the new preview and run it again.", None)

        try:
            backup = backup_database(_db_path(), 'rollover')
        except BackupError as e:
            return False, f"Nothing was changed: the backup could not be made ({e}).", None

        label = state['target_label']
        description = f"Last semester rollover: {label} (by {admin_username})"
        try:
            if not swap_marker(MARKER, state['marker_raw'], format_term(*state['target']), description):
                db.session.rollback()
                return (False, "Another rollover has just been recorded. Nothing was changed.", None)

            # Re-plan INSIDE the transaction (the marker write holds the write lock)
            again = build_plan(state)
            if again['fingerprint'] != plan['fingerprint']:
                db.session.rollback()
                return (False, "The data changed while the rollover was starting. "
                               "Nothing was changed; review the new preview.", None)

            self._complete_rows(again['complete_ids'])
            self._create_rows(again['creates'], state['target'][1], today)
            self._roll_timetable(again['timetable_ids'], again['window'])
            self._sync_students(again['student_ids'], state['target'][1])
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Semester rollover failed: {e}", exc_info=True)
            return (False, "The rollover failed and nothing was changed. "
                           f"The backup is kept at {backup['path']}.", None)

        clear_rollover_memo()
        c = again['counts']
        summary = (f"{c['create']} new enrolment row(s), {c['complete']} row(s) marked Completed, "
                   f"{c['timetable']} timetable entr(ies) rolled, "
                   f"{c['students']} student(s) updated to semester {state['target'][1]}")
        self._log(admin_username, f"Semester rollover for {label} ({again['kind_label']}): {summary}. "
                                  f"Backup: {backup['name']}")
        message = f"Rollover done for {label}: {summary}. Backup: {backup['name']}."
        if again['kind'] == 'to_sem1':
            message += " New semester-1 enrolments are created by the yearly promotion."
        if c['skipped']:
            message += f" {c['skipped']} student(s) got no new row."
        return True, message, {'plan': again, 'backup': backup}

    # ------------------------------------------------------------------
    # Writes (no commit here: run() owns the transaction)
    # ------------------------------------------------------------------

    @staticmethod
    def _complete_rows(ids):
        if ids:
            db.session.execute(text(
                "UPDATE student_courses SET status = 'Completed' "
                "WHERE id = :id AND status = 'Active'"), [{'id': i} for i in ids])

    @staticmethod
    def _create_rows(creates, semester, today=None):
        if creates:
            stamp = (today or date.today()).isoformat()
            db.session.execute(text("""
                INSERT INTO student_courses
                    (student_id, course_code, semester, year, enrollment_date, status)
                VALUES (:student_id, :course_code, :semester, :year, :enrolled, :status)
            """), [{'student_id': c['student_id'], 'course_code': c['course_code'],
                    'semester': semester, 'year': c['year'], 'enrolled': stamp,
                    'status': EnrollmentStatus.ACTIVE} for c in creates])

    @staticmethod
    def _roll_timetable(ids, window):
        if ids:
            db.session.execute(text(
                "UPDATE timetable SET effective_from = :f, effective_to = :t WHERE id = :id"),
                [{'f': window[0].isoformat(), 't': window[1].isoformat(), 'id': i} for i in ids])

    @staticmethod
    def _sync_students(ids, semester):
        if ids:
            db.session.execute(text(
                "UPDATE students SET current_semester = :s WHERE student_id = :id"),
                [{'s': semester, 'id': i} for i in ids])

    @staticmethod
    def _log(admin_username, description):
        """Activity log after the commit; a logging problem never undoes the rollover."""
        try:
            db.session.execute(text("""
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (:user_id, :user_type, :activity_type, :description, :ts)
            """), {'user_id': admin_username, 'user_type': UserType.ADMIN,
                   'activity_type': _activity_type(), 'description': description,
                   'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
            db.session.commit()
        except Exception as e:
            logger.error(f"Rollover activity logging error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass


def _activity_type():
    return getattr(ActivityType, 'SEMESTER_ROLLOVER', 'semester_rollover')