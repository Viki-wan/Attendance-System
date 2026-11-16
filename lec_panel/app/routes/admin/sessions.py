"""
Admin Session Routes (Phase 6a)
Campus-wide session oversight: find any session, see its detail, cancel or
move one that has not been held, and read the lecturer dismissal log.

URL note: session IDs are integers and are always the LAST URL segment. Class
IDs (which contain spaces) only travel as query-string values here.
"""

from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.session_admin_service import (
    DISMISSAL_STATUSES, STATUSES, STATUS_BADGES, STATUS_LABELS, SessionAdminService,
)

admin_sessions_bp = Blueprint('admin_sessions', __name__, url_prefix='/admin/sessions')

service = SessionAdminService()

YEARS = [1, 2, 3, 4, 5, 6]
RANGES = (
    ('upcoming', 'Upcoming'),
    ('today', 'Today'),
    ('week', 'This week'),
    ('past', 'Past'),
    ('all', 'All dates'),
)


def _parse_date(name):
    """ISO date query argument, or None when empty or invalid."""
    raw = request.args.get(name, '').strip()
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _int_arg(name, default=None):
    raw = request.args.get(name, '').strip()
    return int(raw) if raw.isdigit() else default


def _resolve_range():
    """
    (range_key, date_from, date_to, order). Explicit From/To dates win; with
    none, the quick range applies (default: upcoming).
    """
    today = date.today()
    custom_from, custom_to = _parse_date('date_from'), _parse_date('date_to')
    if custom_from or custom_to:
        newest_first = bool(custom_to and custom_to < today)
        return 'custom', custom_from, custom_to, 'desc' if newest_first else 'asc'

    key = request.args.get('range', 'upcoming')
    if key not in dict(RANGES):
        key = 'upcoming'
    if key == 'today':
        return key, today, today, 'asc'
    if key == 'week':
        monday = today - timedelta(days=today.weekday())
        return key, monday, monday + timedelta(days=6), 'asc'
    if key == 'past':
        return key, None, today - timedelta(days=1), 'desc'
    if key == 'all':
        return key, None, None, 'desc'
    return 'upcoming', today, None, 'asc'


# ----------------------------------------------------------------------
# List
# ----------------------------------------------------------------------

@admin_sessions_bp.route('/')
@login_required
@admin_required
def index():
    """Campus-wide session list with filters; no instructor restriction."""
    range_key, date_from, date_to, order = _resolve_range()
    course = request.args.get('course', '').strip() or None
    year = _int_arg('year')
    class_id = request.args.get('class_id', '').strip() or None
    instructor = request.args.get('instructor', '').strip() or None
    status = request.args.get('status', '').strip()
    status = status if status in STATUSES else ''
    page = _int_arg('page', 1)

    result = service.list_sessions(
        date_from=date_from, date_to=date_to, course_code=course, year=year,
        class_id=class_id, instructor_id=instructor, status=status or None,
        order=order, page=page,
    )
    courses, instructors = service.get_filter_options()

    # Links that keep every filter while changing one thing
    keep = dict(
        range=range_key if range_key != 'custom' else None,
        date_from=request.args.get('date_from') or None,
        date_to=request.args.get('date_to') or None,
        course=course, year=year, class_id=class_id, instructor=instructor,
    )

    def link(**changes):
        args = dict(keep, status=status or None)
        args.update(changes)
        return url_for('admin_sessions.index', **{k: v for k, v in args.items() if v})

    status_links = {s: link(status=s, page=None) for s in STATUSES}
    all_status_link = link(status=None, page=None)
    page_links = {
        'prev': link(page=result['page'] - 1) if result['page'] > 1 else None,
        'next': link(page=result['page'] + 1) if result['page'] < result['pages'] else None,
    }

    return render_template(
        'admin/sessions/index.html',
        result=result, rows=result['rows'],
        range_key=range_key, ranges=RANGES,
        date_from=request.args.get('date_from', ''),
        date_to=request.args.get('date_to', ''),
        course=course or '', year=year or '', class_id=class_id or '',
        instructor=instructor or '', status=status,
        courses=courses, instructors=instructors, years=YEARS,
        statuses=STATUSES, status_labels=STATUS_LABELS, status_badges=STATUS_BADGES,
        status_links=status_links, all_status_link=all_status_link,
        page_links=page_links, today=date.today(),
        active_filters=bool(course or year or class_id or instructor or status
                            or range_key not in ('upcoming',)),
    )


# ----------------------------------------------------------------------
# Detail and actions
# ----------------------------------------------------------------------

@admin_sessions_bp.route('/view/<int:session_id>')
@login_required
@admin_required
def view(session_id):
    session = service.get_session(session_id)
    if not session:
        flash('Session not found', 'danger')
        return redirect(url_for('admin_sessions.index'))
    return render_template(
        'admin/sessions/view.html', s=session,
        status_labels=STATUS_LABELS, status_badges=STATUS_BADGES,
    )


@admin_sessions_bp.route('/cancel/<int:session_id>', methods=['POST'])
@login_required
@admin_required
def cancel(session_id):
    success, message = service.cancel_session(
        current_user.username, session_id,
        request.form.get('reason', ''),
        notify=request.form.get('notify') == '1',
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_sessions.view', session_id=session_id))


@admin_sessions_bp.route('/reschedule/<int:session_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def reschedule(session_id):
    session = service.get_session(session_id)
    if not session:
        flash('Session not found', 'danger')
        return redirect(url_for('admin_sessions.index'))
    if not session['can_modify']:
        flash(session['cannot_modify_reason'], 'danger')
        return redirect(url_for('admin_sessions.view', session_id=session_id))

    form_data = {
        'date': session['date_raw'], 'start_time': session['start_time'],
        'end_time': session['end_time'], 'reason': '', 'notify': '1',
        'allow_holiday': '',
    }

    if request.method == 'POST':
        form_data = {
            'date': request.form.get('date', ''),
            'start_time': request.form.get('start_time', ''),
            'end_time': request.form.get('end_time', ''),
            'reason': request.form.get('reason', ''),
            'notify': '1' if request.form.get('notify') == '1' else '',
            'allow_holiday': '1' if request.form.get('allow_holiday') == '1' else '',
        }
        result = service.reschedule_session(
            current_user.username, session_id,
            form_data['date'], form_data['start_time'], form_data['end_time'],
            form_data['reason'],
            allow_holiday=form_data.get('allow_holiday') == '1',
            notify=form_data['notify'] == '1',
        )
        success, message = result[0], result[1]
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('admin_sessions.view', session_id=result[2]))

    return render_template(
        'admin/sessions/reschedule.html', s=session, form_data=form_data,
        status_labels=STATUS_LABELS, status_badges=STATUS_BADGES,
        min_date=date.today().isoformat(),
    )


@admin_sessions_bp.route('/check')
@login_required
@admin_required
def check():
    """Live clash check for the reschedule form (JSON, read-only)."""
    session_id = _int_arg('session_id')
    if session_id is None:
        return jsonify({'error': 'Session not found', 'conflicts': [], 'holiday': None})
    return jsonify(service.check_move(
        session_id,
        request.args.get('date', ''),
        request.args.get('start_time', ''),
        request.args.get('end_time', ''),
    ))


# ----------------------------------------------------------------------
# Lecturer dismissals
# ----------------------------------------------------------------------

@admin_sessions_bp.route('/dismissals')
@login_required
@admin_required
def dismissals():
    status = request.args.get('status', '').strip()
    status = status if status in DISMISSAL_STATUSES else ''
    instructor = request.args.get('instructor', '').strip() or None
    page = _int_arg('page', 1)

    result = service.list_dismissals(status=status or None, instructor_id=instructor, page=page)

    def link(**changes):
        args = dict(status=status or None, instructor=instructor)
        args.update(changes)
        return url_for('admin_sessions.dismissals', **{k: v for k, v in args.items() if v})

    return render_template(
        'admin/sessions/dismissals.html', result=result, rows=result['rows'],
        status=status, instructor=instructor or '',
        dismissal_statuses=DISMISSAL_STATUSES,
        instructors=service.dismissal_instructors(),
        without_record=service.dismissed_without_record(),
        page_links={
            'prev': link(page=result['page'] - 1) if result['page'] > 1 else None,
            'next': link(page=result['page'] + 1) if result['page'] < result['pages'] else None,
        },
        status_labels=STATUS_LABELS, status_badges=STATUS_BADGES,
    )