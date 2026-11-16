"""
Yearly Promotion Service (Phase 7d)

What a promotion does, once per academic year, after the autumn semester rollover:

  * every active student moves up one year of study (``students.year_of_study`` + 1);
  * active students already in the final year (setting ``final_year_of_study``, default 4)
    graduate: ``is_active = 0`` (reversible, nothing is deleted);
  * students the admin HOLDS BACK (repeaters, deferrals) keep their year;
  * every student who stays active gets a semester-1 ``student_courses`` row for the new
    academic year at their new (or unchanged) year of study. A held-back student's row
    for that year already exists from last year (the unique key is student / course /
    semester / year, there is no academic-year column), so a ``Completed`` or ``Failed``
    row is REOPENED (status back to ``Active``) instead of inserted. A ``Dropped`` row is
    never reopened automatically and the student is listed as skipped.

Design notes (same pattern as the 7c rollover; match the live data, not the ORM):

- "Due" is decided by a stored marker ``marker_promotion`` = the academic year the students
  are currently promoted for (``2026``; ``markers.parse_term('2026') -> (2026, None)``).
  There is no way to know from the data which year a never-promoted campus is in, so with
  no marker the page offers ONE explicit step, "record the current academic year", and
  nothing is ever due until that is done. The marker protects against running twice.
- Promotion is offered only when the semester rollover has already put the campus in
  semester 1 of the new academic year (``marker_rollover`` == ``<year>:1``), so the
  semester-2 rows are Completed first. Until then the state is "waiting".
- A marker later than the calendar's year ("reversed"), unreadable, or more than one year
  behind ("skipped a year") is never offered: the page explains and offers nothing.
- ``build_plan`` reads only; it is the preview. ``run`` re-plans, refuses if the plan no
  longer matches the previewed one (fingerprint, which covers the hold-back selection),
  writes a verified backup, then does everything in ONE transaction that starts with a
  compare-and-swap of the marker. The activity log row is written after the commit.
- Promotion changes no sessions, no timetable entries and no attendance. Class membership
  is course + year of study, so promoted students move to the next year's classes by
  design (the preview shows the movement per course and year).
- Plain ``text()`` SQL throughout.
"""

import csv
import hashlib
import io
import json
import logging
import re
from collections import Counter
from datetime import date, datetime

from flask import g, has_app_context
from sqlalchemy import text

from app import db
from app.services.rollover_service import MARKER as ROLLOVER_MARKER
from app.services.settings_admin_service import get_setting
from app.utils import academic_calendar as calendar
from app.utils import calendar_rules as rules
from app.utils.db_backup import BackupError, backup_database, default_backup_dir
from app.utils.markers import format_term, parse_term, read_marker, read_marker_info, swap_marker
from config.constants import ActivityType, EnrollmentStatus, UserType

logger = logging.getLogger(__name__)

MARKER = 'promotion'
MAX_SKIPPED_SHOWN = 50
MAX_HELD_IN_LOG = 30

SKIP_REASONS = {
    'no_course': "The student has no course",
    'course_missing': "The student's course is not in the course list",
    'already_present': "An active semester 1 row for the new year already exists",
    'dropped': "A dropped row for that year exists (not reopened automatically)",
}


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def _scalar(sql, params=None):
    return db.session.execute(text(sql), params or {}).scalar()


def _db_path():
    return db.engine.url.database


def _safe_cell(value):
    """Spreadsheet-injection defence, same rule as the 6c exports and the 7c CSV."""
    s = '' if value is None else str(value)
    return "'" + s if s[:1] in ('=', '+', '-', '@', '\t', '\r') else s


def _activity_type():
    return getattr(ActivityType, 'YEARLY_PROMOTION', 'yearly_promotion')


def parse_hold_text(raw):
    """Student IDs pasted by the admin: one per line, or separated by commas / semicolons."""
    out = []
    for part in re.split(r'[\r\n,;]+', raw or ''):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


# ----------------------------------------------------------------------
# State: is a promotion due?  (call time, memoised per request, never raises)
# ----------------------------------------------------------------------

def compute_state(today=None):
    """
    ``{'academic_year', 'label', 'last_year', 'marker_raw', 'status', 'due', 'blocked',
    'reversed', 'waiting', 'needs_baseline', 'level', 'message'}``. Reads only.
    ``status`` is one of: due, done, needs_baseline, waiting, blocked, reversed.
    """
    ay = calendar.get_academic_year(today)
    sem = calendar.get_current_semester(today)
    label = rules.year_label(ay)
    info = read_marker_info(MARKER)
    raw = info['value'] if info else None

    state = {'academic_year': ay, 'label': label, 'last_year': None, 'marker_raw': raw,
             'status': 'done', 'due': False, 'blocked': False, 'reversed': False,
             'waiting': False, 'needs_baseline': False, 'level': 'success', 'message': ''}

    def finish(status, level, message, **flags):
        state.update(status=status, level=level, message=message, **flags)
        return state

    if raw is None:
        return finish('needs_baseline', 'warning', (
            f"No yearly promotion has been recorded yet. Record {label} as the academic year the "
            f"students' years of study are currently correct for, so the next promotion can be "
            f"offered when the new year starts. Do this only if the years of study already "
            f"match {label}."), needs_baseline=True)

    last = parse_term(raw)
    if last is None or last[1] is not None:
        return finish('blocked', 'danger', (
            "The stored promotion marker is unreadable, so no promotion is offered. "
            "It needs a look before anything is run."), blocked=True)

    last_year = last[0]
    state['last_year'] = last_year
    last_label = rules.year_label(last_year)

    if last_year == ay:
        return finish('done', 'success',
                      f"Students are promoted for {label}. Nothing to do until the next academic year starts.")
    if last_year > ay:
        return finish('reversed', 'warning', (
            f"A promotion was already recorded for {last_label}, but the calendar now places today in "
            f"{label}. Nothing is reversed and nothing is offered. Check the calendar dates on the settings page."),
            reversed=True)
    if ay - last_year > 1:
        return finish('blocked', 'danger', (
            f"The last promotion was for {last_label} but the campus is now in {label}. That skips at "
            f"least one academic year, so it cannot be done in one step. Do not edit years of study by "
            f"hand before this is sorted out."), blocked=True)

    # Exactly one academic year behind: a promotion is expected. Is the campus ready?
    roll = parse_term(read_marker(ROLLOVER_MARKER)) if read_marker(ROLLOVER_MARKER) else None
    if sem != 1 or roll != (ay, 1):
        return finish('waiting', 'info', (
            f"A new academic year ({label}) has started. Run the semester rollover first so the old "
            f"semester 2 enrolments are completed; the promotion is offered once the rollover has "
            f"recorded {label} semester 1."), waiting=True)

    return finish('due', 'warning', (
        f"Yearly promotion due: the campus is in {label} but students are still promoted for {last_label}."),
        due=True)


def _memo_get():
    if has_app_context():
        return getattr(g, '_promotion_state_memo', None)
    return None


def clear_promotion_memo():
    if has_app_context() and hasattr(g, '_promotion_state_memo'):
        g._promotion_state_memo = None


def get_promotion_state():
    """Reader for the dashboard and settings page. Memoised per request, never raises."""
    memo = _memo_get()
    if memo is not None:
        return memo
    try:
        state = compute_state()
    except Exception as e:
        logger.error(f"Could not check whether a promotion is due: {e}")
        return {'due': False, 'blocked': False, 'reversed': False, 'waiting': False,
                'needs_baseline': False, 'error': True, 'status': 'error',
                'level': 'secondary', 'message': "Could not check whether a promotion is due."}
    if has_app_context():
        g._promotion_state_memo = state
    return state


# ----------------------------------------------------------------------
# Plan (reads only; also the preview)
# ----------------------------------------------------------------------

def build_plan(state, hold_ids=None):
    """What a promotion would do for a due ``state``, holding back ``hold_ids``. Writes nothing."""
    ay = state['academic_year']
    final_year = int(get_setting('final_year_of_study'))
    window_start = calendar.get_year_windows(ay)[1][0].isoformat()
    wanted = set(hold_ids or ())

    courses = {r[0] for r in db.session.execute(text("SELECT course_code FROM courses")).all()}
    class_years = {(r[0], int(r[1])) for r in db.session.execute(text(
        "SELECT DISTINCT course_code, year FROM classes WHERE is_active = 1 AND year IS NOT NULL")).all()}
    sem1_rows = {}
    for rid, sid, cc, yr, st in db.session.execute(text(
            "SELECT id, student_id, course_code, year, status FROM student_courses "
            "WHERE semester = 1 AND year IS NOT NULL")).all():
        sem1_rows[(sid, cc, int(yr))] = (int(rid), st)

    students = db.session.execute(text(
        "SELECT student_id, fname, lname, course, year_of_study, created_at FROM students "
        "WHERE is_active = 1 ORDER BY course, year_of_study, student_id")).all()
    known_ids = {s[0] for s in students}
    holds = wanted & known_ids
    unknown_holds = sorted(wanted - known_ids)

    people, promote, graduate, held, untouched = [], [], [], [], []
    creates, reopens, skipped = [], [], []
    now_count, stay_count, out_count, in_count = Counter(), Counter(), Counter(), Counter()
    new_since_start = 0

    for sid, fname, lname, course, year, created in students:
        code = (course or '').strip()
        name = f"{fname or ''} {lname or ''}".strip()
        is_new = bool(created) and str(created)[:10] >= window_start
        new_since_start += 1 if is_new else 0
        person = {'student_id': sid, 'name': name, 'course_code': code, 'year': year,
                  'held': sid in holds, 'new': is_new, 'action': '', 'new_year': None,
                  'enrolment': ''}
        people.append(person)

        try:
            y = int(year)
        except (TypeError, ValueError):
            y = 0
        if y < 1:
            person.update(action='untouched', enrolment="No year of study: left as it is")
            untouched.append(person)
            continue

        now_count[(code, y)] += 1
        if sid in holds:
            action, new_year = 'hold', y
            held.append(person)
            stay_count[(code, y)] += 1
        elif y >= final_year:
            action, new_year = 'graduate', None
            graduate.append(person)
            out_count[(code, y)] += 1
        else:
            action, new_year = 'promote', y + 1
            promote.append(person)
            out_count[(code, y)] += 1
            in_count[(code, y + 1)] += 1
        person.update(action=action, new_year=new_year)
        if action == 'graduate':
            person['enrolment'] = 'None (graduating)'
            continue

        # Semester-1 row for the new academic year at the new (or unchanged) year
        reason = None
        if not code:
            reason = 'no_course'
        elif code not in courses:
            reason = 'course_missing'
        else:
            existing = sem1_rows.get((sid, code, new_year))
            if existing is None:
                creates.append({'student_id': sid, 'course_code': code, 'year': new_year})
                person['enrolment'] = 'New row'
            elif existing[1] in ('Completed', 'Failed'):
                reopens.append({'id': existing[0], 'student_id': sid, 'course_code': code,
                                'year': new_year, 'was': existing[1]})
                person['enrolment'] = f"Reopened ({existing[1]} row)"
            elif existing[1] == 'Active':
                reason = 'already_present'
            else:
                reason = 'dropped'
        if reason:
            person['enrolment'] = SKIP_REASONS[reason]
            skipped.append({'student_id': sid, 'course_code': code, 'year': new_year,
                            'reason': reason, 'reason_text': SKIP_REASONS[reason]})

    # Movement per course and year (membership = course + year of study)
    keys = set(now_count) | set(in_count) | set(stay_count)
    movement = []
    for code, y in sorted(keys, key=lambda k: (k[0] or '~', k[1])):
        after = stay_count[(code, y)] + in_count[(code, y)]
        movement.append({
            'course_code': code or '(no course)', 'year': y,
            'now': now_count[(code, y)], 'leaving': out_count[(code, y)],
            'staying': stay_count[(code, y)], 'arriving': in_count[(code, y)], 'after': after,
            'has_class': (code, y) in class_years,
            # Only a real course can lack a class; no-course / unknown-course students have none by definition
            'warn': after > 0 and code in courses and (code, y) not in class_years,
        })

    # Checklist grouped by cohort
    cohorts = {}
    for p in people:
        if p['action'] == 'untouched':
            continue
        cohorts.setdefault((p['course_code'], int(p['year'])), []).append(p)
    cohort_list = [{'course_code': k[0] or '(no course)', 'year': k[1], 'students': v,
                    'held': sum(1 for s in v if s['held'])}
                   for k, v in sorted(cohorts.items(), key=lambda kv: (kv[0][0] or '~', kv[0][1]))]

    by_reason = Counter(s['reason'] for s in skipped)
    payload = json.dumps({
        'ay': ay, 'last': state['marker_raw'], 'roll': read_marker(ROLLOVER_MARKER),
        'final': final_year, 'holds': sorted(holds),
        'p': [[p['student_id'], p['year'], p['new_year']] for p in promote],
        'g': [p['student_id'] for p in graduate],
        'u': [p['student_id'] for p in untouched],
        'c': [[c['student_id'], c['course_code'], c['year']] for c in creates],
        'r': [r['id'] for r in reopens],
    }, sort_keys=True)

    return {
        'academic_year': ay, 'label': state['label'], 'final_year': final_year,
        'window_start': window_start, 'people': people,
        'promote': promote, 'graduate': graduate, 'held': held, 'untouched': untouched,
        'creates': creates, 'reopens': reopens, 'skipped': skipped,
        'unknown_holds': unknown_holds, 'hold_ids': sorted(holds),
        'movement': movement, 'cohorts': cohort_list,
        'counts': {
            'students': len(students), 'promote': len(promote), 'graduate': len(graduate),
            'held': len(held), 'untouched': len(untouched), 'create': len(creates),
            'reopen': len(reopens), 'skipped': len(skipped), 'skipped_by_reason': dict(by_reason),
            'new_since_start': new_since_start,
            'no_class': sum(1 for m in movement if m['warn']),
            'inactive_students': int(_scalar(
                "SELECT COUNT(*) FROM students WHERE is_active = 0 OR is_active IS NULL") or 0),
        },
        'fingerprint': hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16],
    }


def _csv_bytes(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\r\n')
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe_cell(c) for c in row])
    return ('\ufeff' + buf.getvalue()).encode('utf-8')   # BOM so Excel reads UTF-8


def skipped_csv(plan):
    """Students who stay active but get no new / reopened row, and why."""
    return _csv_bytes(['student_id', 'course', 'year_of_study_after', 'reason'],
                      [[s['student_id'], s['course_code'], s['year'], s['reason_text']]
                       for s in plan['skipped']])


def full_csv(plan):
    """Every active student with what the promotion would do. Keep it as the record of the run."""
    labels = {'promote': 'Promote', 'graduate': 'Graduate (deactivate)',
              'hold': 'Held back', 'untouched': 'Left as it is'}
    return _csv_bytes(
        ['student_id', 'name', 'course', 'year_now', 'outcome', 'year_after', 'enrolment'],
        [[p['student_id'], p['name'], p['course_code'], p['year'], labels.get(p['action'], ''),
          '' if p['new_year'] is None else p['new_year'], p['enrolment']] for p in plan['people']])


# ----------------------------------------------------------------------
# Service used by the pages
# ----------------------------------------------------------------------

class PromotionService:

    def page(self, hold_ids=None, pasted_text='', today=None):
        """Everything the promotion page needs. ``hold_ids`` = ticked boxes, ``pasted_text`` = pasted IDs."""
        state = compute_state(today)
        plan, notes = None, []
        if state['due']:
            holds = list(hold_ids or []) + parse_hold_text(pasted_text)
            plan = build_plan(state, holds)
            if plan['unknown_holds']:
                shown = ', '.join(plan['unknown_holds'][:10])
                more = len(plan['unknown_holds']) - 10
                notes.append("Not held back (not an active student): " + shown
                             + (f" and {more} more" if more > 0 else ""))
        try:
            backup_dir = str(default_backup_dir(_db_path()))
        except Exception:
            backup_dir = ''
        return {
            'state': state, 'plan': plan, 'notes': notes,
            'skipped_shown': plan['skipped'][:MAX_SKIPPED_SHOWN] if plan else [],
            'max_skipped_shown': MAX_SKIPPED_SHOWN,
            'marker': read_marker_info(MARKER), 'recent': self.recent_runs(),
            'backup_dir': backup_dir,
        }

    def export_csv(self, kind, hold_ids=None, today=None):
        """``(bytes, filename)`` or None when no promotion is due."""
        state = compute_state(today)
        if not state['due']:
            return None
        plan = build_plan(state, hold_ids)
        stamp = (today or date.today()).strftime('%Y%m%d')
        if kind == 'skipped':
            return skipped_csv(plan), f"promotion_skipped_{stamp}.csv"
        return full_csv(plan), f"promotion_list_{stamp}.csv"

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
            logger.error(f"Could not list recent promotions: {e}")
            return []

    # ------------------------------------------------------------------

    def record_baseline(self, admin_username, today=None):
        """
        One-off: record the current academic year as the one students are promoted for.
        Writes only the marker (compare-and-swap, nothing else to protect). Returns ``(ok, message)``.
        """
        state = compute_state(today)
        if not state['needs_baseline']:
            return False, state['message'] or "A baseline is already recorded."
        label = state['label']
        description = f"Students promoted for: {label} (recorded by {admin_username})"
        try:
            if not swap_marker(MARKER, None, format_term(state['academic_year']), description):
                db.session.rollback()
                return False, "A promotion marker was just recorded by someone else. Nothing was changed."
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Recording the promotion baseline failed: {e}", exc_info=True)
            return False, "Could not record it. Nothing was changed."
        clear_promotion_memo()
        self._log(admin_username, f"Yearly promotion baseline recorded: students are taken to be "
                                  f"promoted for {label}. No student was changed.")
        return True, (f"Recorded {label} as the academic year students are promoted for. "
                      f"The next promotion is offered when the next academic year starts.")

    def run(self, admin_username, fingerprint, hold_ids=None, today=None):
        """
        Run the promotion the admin previewed. Returns ``(success, message, result)``.

        Order: check due -> check the preview (and hold-back selection) is still current ->
        backup (a failed backup stops everything) -> ONE transaction: compare-and-swap the
        marker, re-plan, compare again, write -> commit -> log. Any failure rolls back.
        """
        state = compute_state(today)
        if not state['due']:
            return False, state['message'] or "No promotion is due.", None

        plan = build_plan(state, hold_ids)
        if not fingerprint or fingerprint != plan['fingerprint']:
            return (False, "The data or the hold-back selection changed since the preview was made. "
                           "Nothing was changed; press Update preview, check it, and run it again.", None)

        try:
            backup = backup_database(_db_path(), 'promotion')
        except BackupError as e:
            return False, f"Nothing was changed: the backup could not be made ({e}).", None

        label = state['label']
        description = f"Students promoted for: {label} (by {admin_username})"
        try:
            if not swap_marker(MARKER, state['marker_raw'], format_term(state['academic_year']), description):
                db.session.rollback()
                return False, "Another promotion has just been recorded. Nothing was changed.", None

            # Re-plan INSIDE the transaction (the marker write holds the write lock)
            again = build_plan(state, hold_ids)
            if again['fingerprint'] != plan['fingerprint']:
                db.session.rollback()
                return (False, "The data changed while the promotion was starting. "
                               "Nothing was changed; review the new preview.", None)

            self._promote(again['promote'])
            self._graduate(again['graduate'])
            self._reopen_rows(again['reopens'])
            self._create_rows(again['creates'], today)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Yearly promotion failed: {e}", exc_info=True)
            return (False, "The promotion failed and nothing was changed. "
                           f"The backup is kept at {backup['path']}.", None)

        clear_promotion_memo()
        c = again['counts']
        summary = (f"{c['promote']} promoted, {c['graduate']} graduated (deactivated), "
                   f"{c['held']} held back, {c['create']} new enrolment row(s), "
                   f"{c['reopen']} row(s) reopened")
        held_text = ''
        if again['hold_ids']:
            shown = again['hold_ids'][:MAX_HELD_IN_LOG]
            more = len(again['hold_ids']) - len(shown)
            held_text = " Held back: " + ', '.join(shown) + (f" and {more} more." if more > 0 else ".")
        self._log(admin_username, f"Yearly promotion for {label}: {summary}.{held_text} "
                                  f"Backup: {backup['name']}")
        message = f"Promotion done for {label}: {summary}. Backup: {backup['name']}."
        if c['skipped']:
            message += f" {c['skipped']} student(s) got no new enrolment row."
        return True, message, {'plan': again, 'backup': backup}

    # ------------------------------------------------------------------
    # Writes (no commit here: run() owns the transaction)
    # ------------------------------------------------------------------

    @staticmethod
    def _promote(people):
        if people:
            db.session.execute(text(
                "UPDATE students SET year_of_study = :y WHERE student_id = :id AND is_active = 1"),
                [{'y': p['new_year'], 'id': p['student_id']} for p in people])

    @staticmethod
    def _graduate(people):
        if people:
            db.session.execute(text(
                "UPDATE students SET is_active = 0 WHERE student_id = :id"),
                [{'id': p['student_id']} for p in people])

    @staticmethod
    def _reopen_rows(rows):
        if rows:
            db.session.execute(text(
                "UPDATE student_courses SET status = 'Active' "
                "WHERE id = :id AND status IN ('Completed', 'Failed')"),
                [{'id': r['id']} for r in rows])

    @staticmethod
    def _create_rows(creates, today=None):
        if creates:
            stamp = (today or date.today()).isoformat()
            db.session.execute(text("""
                INSERT INTO student_courses
                    (student_id, course_code, semester, year, enrollment_date, status)
                VALUES (:student_id, :course_code, 1, :year, :enrolled, :status)
            """), [{'student_id': c['student_id'], 'course_code': c['course_code'],
                    'year': c['year'], 'enrolled': stamp,
                    'status': EnrollmentStatus.ACTIVE} for c in creates])

    @staticmethod
    def _log(admin_username, description):
        """Activity log after the commit; a logging problem never undoes the promotion."""
        try:
            db.session.execute(text("""
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (:user_id, :user_type, :activity_type, :description, :ts)
            """), {'user_id': admin_username, 'user_type': UserType.ADMIN,
                   'activity_type': _activity_type(), 'description': description,
                   'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
            db.session.commit()
        except Exception as e:
            logger.error(f"Promotion activity logging error: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass