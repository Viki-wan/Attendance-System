"""
Admin Attendance Routes (Phase 6b + 6c)
Campus-wide attendance: held sessions (by session and by date range), by class,
by student, the session sheet with admin corrections, the corrections log, and
(6c) CSV / Excel / PDF exports of those views.

URL note: session IDs are integers. Student IDs contain slashes, so they use a
<path:> converter and are always the LAST URL segment. Class IDs contain spaces,
so they only travel as query-string values.
"""

import io
import logging
from datetime import date, timedelta

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, send_file, url_for,
)
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.attendance_admin_service import (
    CORRECTABLE_STATUS, HELD_STATUSES, MAX_REASON, STATUS_BADGES, STATUSES,
    AttendanceAdminService,
)
from app.services.settings_admin_service import get_low_threshold
from app.services.attendance_export_service import (
    PDF_REPORTS, AttendanceExportService, ExportError, pdf_installed,
)

logger = logging.getLogger(__name__)

admin_attendance_bp = Blueprint('admin_attendance', __name__, url_prefix='/admin/attendance')

service = AttendanceAdminService()
export_service = AttendanceExportService()

YEARS = [1, 2, 3, 4, 5, 6]
RANGES = (
    ('all', 'All dates'),
    ('week', 'Last 7 days'),
    ('month', 'Last 30 days'),
)
SESSION_STATUS_BADGES = {'completed': 'secondary', 'ongoing': 'success'}
SESSION_STATUS_LABELS = {'completed': 'Completed', 'ongoing': 'Ongoing'}
EXPORT_FORMATS = ('csv', 'xlsx', 'pdf')


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
    """(range_key, date_from, date_to). Explicit dates win over the quick range."""
    today = date.today()
    custom_from, custom_to = _parse_date('date_from'), _parse_date('date_to')
    if custom_from or custom_to:
        return 'custom', custom_from, custom_to
    key = request.args.get('range', 'all')
    if key not in dict(RANGES):
        key = 'all'
    if key == 'week':
        return key, today - timedelta(days=6), today
    if key == 'month':
        return key, today - timedelta(days=29), today
    return 'all', None, None


def _filter_context():
    """The filters every list shares, parsed once."""
    range_key, date_from, date_to = _resolve_range()
    return {
        'range_key': range_key, 'date_from': date_from, 'date_to': date_to,
        'course': request.args.get('course', '').strip() or None,
        'year': _int_arg('year'),
        'class_id': request.args.get('class_id', '').strip() or None,
    }


def _form_values(f):
    """Filter values as the templates echo them back into the form."""
    return dict(
        range_key=f['range_key'],
        date_from=request.args.get('date_from', ''),
        date_to=request.args.get('date_to', ''),
        course=f['course'] or '', year=f['year'] or '', class_id=f['class_id'] or '',
    )


def _keep(f):
    """Query arguments that preserve the current filters in generated links."""
    return dict(
        range=f['range_key'] if f['range_key'] != 'custom' else None,
        date_from=request.args.get('date_from') or None,
        date_to=request.args.get('date_to') or None,
        course=f['course'], year=f['year'], class_id=f['class_id'],
    )


def _linker(endpoint, base, **fixed):
    def link(**changes):
        args = dict(base, **fixed)
        args.update(changes)
        return url_for(endpoint, **{k: v for k, v in args.items() if v})
    return link


def _page_links(link, page, pages):
    return {
        'prev': link(page=page - 1) if page > 1 else None,
        'next': link(page=page + 1) if page < pages else None,
    }


# ----------------------------------------------------------------------
# Export helpers (6c)
# ----------------------------------------------------------------------

def _export_links(endpoint, args, pdf=False, **fixed):
    """{'csv': url, 'xlsx': url, 'pdf': url?} for the Export buttons, keeping the page's filters."""
    formats = ['csv', 'xlsx'] + (['pdf'] if pdf and pdf_installed() else [])
    clean = {k: v for k, v in dict(args, **fixed).items() if v}
    return {fmt: url_for(endpoint, fmt=fmt, **clean) for fmt in formats}


def _export(build, fmt, back, pdf_allowed=False):
    """Build the report and send it, or flash the reason and go back to the page."""
    if fmt not in EXPORT_FORMATS or (fmt == 'pdf' and not pdf_allowed):
        abort(404)
    try:
        report = build()
        data, mimetype = export_service.render(report, fmt)
        export_service.log_export(current_user.username, report, fmt)
        return send_file(io.BytesIO(data), mimetype=mimetype, as_attachment=True,
                         download_name=export_service.filename(report, fmt))
    except ExportError as e:
        flash(str(e), 'danger')
    except Exception:
        logger.exception("Attendance export failed")
        flash('Could not create the export', 'danger')
    return redirect(back)


# ----------------------------------------------------------------------
# Held sessions (by session and by date range)
# ----------------------------------------------------------------------

@admin_attendance_bp.route('/')
@login_required
@admin_required
def index():
    f = _filter_context()
    status = request.args.get('status', '').strip()
    status = status if status in HELD_STATUSES else ''
    low = request.args.get('low') == '1'
    page = _int_arg('page', 1)

    result = service.list_held_sessions(
        date_from=f['date_from'], date_to=f['date_to'], course_code=f['course'],
        year=f['year'], class_id=f['class_id'], status=status or None,
        low_only=low, page=page,
    )
    courses, _ = service.get_filter_options()

    link = _linker('admin_attendance.index', _keep(f), status=status or None,
                   low='1' if low else None)
    return render_template(
        'admin/attendance/index.html',
        result=result, rows=result['rows'], f=_form_values(f), ranges=RANGES,
        courses=courses, years=YEARS, status=status, low=low,
        threshold=get_low_threshold(), statuses=HELD_STATUSES,
        status_labels=SESSION_STATUS_LABELS, status_badges=SESSION_STATUS_BADGES,
        status_links={s: link(status=s, page=None) for s in HELD_STATUSES},
        all_status_link=link(status=None, page=None),
        low_link=link(low=None if low else '1', page=None),
        page_links=_page_links(link, result['page'], result['pages']),
        export_links=_export_links('admin_attendance.export_sessions', _keep(f),
                                   status=status or None, low='1' if low else None),
        active_filters=bool(f['course'] or f['year'] or f['class_id'] or status or low
                            or f['range_key'] != 'all'),
    )


# ----------------------------------------------------------------------
# By class
# ----------------------------------------------------------------------

@admin_attendance_bp.route('/classes')
@login_required
@admin_required
def classes():
    f = _filter_context()
    sort = 'rate' if request.args.get('sort') == 'rate' else 'class'
    low = request.args.get('low') == '1'
    rows = service.class_summaries(
        date_from=f['date_from'], date_to=f['date_to'], course_code=f['course'],
        year=f['year'], class_id=f['class_id'], sort=sort, low_only=low,
    )
    courses, _ = service.get_filter_options()
    link = _linker('admin_attendance.classes', _keep(f), sort=sort if sort != 'class' else None,
                   low='1' if low else None)
    return render_template(
        'admin/attendance/classes.html', rows=rows, f=_form_values(f), ranges=RANGES,
        courses=courses, years=YEARS, sort=sort, low=low, threshold=get_low_threshold(),
        sort_link=link(sort=None if sort == 'rate' else 'rate'),
        low_link=link(low=None if low else '1'),
        keep=_keep(f),
        export_links=_export_links('admin_attendance.export_classes', _keep(f),
                                   sort='rate' if sort == 'rate' else None,
                                   low='1' if low else None),
        active_filters=bool(f['course'] or f['year'] or f['class_id'] or low
                            or f['range_key'] != 'all'),
    )


@admin_attendance_bp.route('/class')
@login_required
@admin_required
def class_view():
    class_id = request.args.get('class_id', '').strip()
    range_key, date_from, date_to = _resolve_range()
    sort = 'rate' if request.args.get('sort') == 'rate' else 'student'
    detail = service.class_detail(class_id, date_from, date_to, sort=sort) if class_id else None
    if not detail:
        flash('Class not found', 'danger')
        return redirect(url_for('admin_attendance.classes'))
    keep = dict(class_id=class_id,
                range=range_key if range_key != 'custom' else None,
                date_from=request.args.get('date_from') or None,
                date_to=request.args.get('date_to') or None)
    link = _linker('admin_attendance.class_view', keep)
    return render_template(
        'admin/attendance/class_view.html', d=detail, ranges=RANGES, range_key=range_key,
        date_from=request.args.get('date_from', ''), date_to=request.args.get('date_to', ''),
        sort=sort, sort_link=link(sort=None if sort == 'rate' else 'rate'),
        threshold=get_low_threshold(), session_badges=SESSION_STATUS_BADGES,
        session_labels=SESSION_STATUS_LABELS,
        export_links=_export_links('admin_attendance.export_class', keep, pdf=True,
                                   sort='rate' if sort == 'rate' else None),
    )


# ----------------------------------------------------------------------
# By student
# ----------------------------------------------------------------------

@admin_attendance_bp.route('/students')
@login_required
@admin_required
def students():
    q = request.args.get('q', '').strip()
    course = request.args.get('course', '').strip() or None
    year = _int_arg('year')
    low = request.args.get('low') == '1'
    page = _int_arg('page', 1)
    result = service.list_students(query=q or None, course_code=course, year=year,
                                   low_only=low, page=page)
    courses, _ = service.get_filter_options()
    link = _linker('admin_attendance.students',
                   dict(q=q or None, course=course, year=year), low='1' if low else None)
    return render_template(
        'admin/attendance/students.html', result=result, rows=result['rows'], q=q,
        course=course or '', year=year or '', low=low, courses=courses, years=YEARS,
        threshold=get_low_threshold(), low_link=link(low=None if low else '1', page=None),
        page_links=_page_links(link, result['page'], result['pages']),
        export_links=_export_links('admin_attendance.export_students',
                                   dict(q=q or None, course=course, year=year),
                                   low='1' if low else None),
        active_filters=bool(q or course or year or low),
    )


@admin_attendance_bp.route('/student/<path:student_id>')
@login_required
@admin_required
def student_view(student_id):
    range_key, date_from, date_to = _resolve_range()
    page = _int_arg('page', 1)
    data = service.get_student(student_id, date_from, date_to, page=page)
    if not data:
        flash('Student not found', 'danger')
        return redirect(url_for('admin_attendance.students'))
    keep = dict(range=range_key if range_key != 'custom' else None,
                date_from=request.args.get('date_from') or None,
                date_to=request.args.get('date_to') or None)
    link = _linker('admin_attendance.student_view', keep, student_id=student_id)
    return render_template(
        'admin/attendance/student_view.html', d=data, ranges=RANGES, range_key=range_key,
        date_from=request.args.get('date_from', ''), date_to=request.args.get('date_to', ''),
        status_badges=STATUS_BADGES, threshold=get_low_threshold(),
        session_badges=SESSION_STATUS_BADGES, session_labels=SESSION_STATUS_LABELS,
        page_links=_page_links(link, data['page'], data['pages']),
        export_links=_export_links('admin_attendance.export_student', keep,
                                   student_id=student_id),
    )


# ----------------------------------------------------------------------
# Session sheet and corrections
# ----------------------------------------------------------------------

@admin_attendance_bp.route('/session/<int:session_id>')
@login_required
@admin_required
def sheet(session_id):
    data = service.get_sheet(session_id)
    if not data:
        flash('Session not found', 'danger')
        return redirect(url_for('admin_attendance.index'))
    held = data['session']['status'] in HELD_STATUSES
    return render_template(
        'admin/attendance/sheet.html', d=data, statuses=STATUSES,
        status_badges=STATUS_BADGES, session_badges=SESSION_STATUS_BADGES,
        session_labels=SESSION_STATUS_LABELS, threshold=get_low_threshold(),
        max_reason=MAX_REASON, correctable=CORRECTABLE_STATUS,
        export_links=(_export_links('admin_attendance.export_session', {}, pdf=True,
                                    session_id=session_id) if held else None),
    )


@admin_attendance_bp.route('/session/<int:session_id>/correct', methods=['POST'])
@login_required
@admin_required
def correct(session_id):
    """Apply one status to the selected students. Each value is 'student_id|seen_status'."""
    items = []
    for raw in request.form.getlist('rows'):
        student_id, _, seen_status = raw.rpartition('|')
        if student_id:
            items.append((student_id, seen_status))
    success, message, _ = service.correct(
        current_user.username, session_id, items,
        request.form.get('status', ''), request.form.get('reason', ''),
        notify=request.form.get('notify') == '1',
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_attendance.sheet', session_id=session_id))


# ----------------------------------------------------------------------
# Corrections log
# ----------------------------------------------------------------------

@admin_attendance_bp.route('/corrections')
@login_required
@admin_required
def corrections():
    who = 'all' if request.args.get('who') == 'all' else 'admin'
    q = request.args.get('q', '').strip()
    page = _int_arg('page', 1)
    result = service.list_corrections(who=who, query=q or None, page=page)
    link = _linker('admin_attendance.corrections',
                   dict(q=q or None), who='all' if who == 'all' else None)
    return render_template(
        'admin/attendance/corrections.html', result=result, rows=result['rows'],
        who=who, q=q, who_link=link(who=None if who == 'all' else 'all', page=None),
        page_links=_page_links(link, result['page'], result['pages']),
    )


# ----------------------------------------------------------------------
# Exports (6c): same filters as the pages, fmt = csv | xlsx | pdf
# PDF is offered only for the session sheet and the class page (PDF_REPORTS).
# ----------------------------------------------------------------------

@admin_attendance_bp.route('/export/sessions/<fmt>')
@login_required
@admin_required
def export_sessions(fmt):
    f = _filter_context()
    status = request.args.get('status', '').strip()
    status = status if status in HELD_STATUSES else ''
    low = request.args.get('low') == '1'
    back = _linker('admin_attendance.index', _keep(f), status=status or None,
                   low='1' if low else None)()
    return _export(lambda: export_service.sessions_report(
        date_from=f['date_from'], date_to=f['date_to'], course_code=f['course'],
        year=f['year'], class_id=f['class_id'], status=status or None, low_only=low),
        fmt, back)


@admin_attendance_bp.route('/export/classes/<fmt>')
@login_required
@admin_required
def export_classes(fmt):
    f = _filter_context()
    sort = 'rate' if request.args.get('sort') == 'rate' else 'class'
    low = request.args.get('low') == '1'
    back = _linker('admin_attendance.classes', _keep(f), sort=sort if sort != 'class' else None,
                   low='1' if low else None)()
    return _export(lambda: export_service.classes_report(
        date_from=f['date_from'], date_to=f['date_to'], course_code=f['course'],
        year=f['year'], class_id=f['class_id'], sort=sort, low_only=low),
        fmt, back)


@admin_attendance_bp.route('/export/class/<fmt>')
@login_required
@admin_required
def export_class(fmt):
    class_id = request.args.get('class_id', '').strip()
    range_key, date_from, date_to = _resolve_range()
    sort = 'rate' if request.args.get('sort') == 'rate' else 'student'
    if not class_id:
        flash('Class not found', 'danger')
        return redirect(url_for('admin_attendance.classes'))
    back = url_for('admin_attendance.class_view', class_id=class_id,
                   **{k: v for k, v in dict(
                       range=range_key if range_key != 'custom' else None,
                       date_from=request.args.get('date_from') or None,
                       date_to=request.args.get('date_to') or None).items() if v})
    return _export(lambda: export_service.class_report(class_id, date_from, date_to, sort=sort),
                   fmt, back, pdf_allowed='class' in PDF_REPORTS)


@admin_attendance_bp.route('/export/students/<fmt>')
@login_required
@admin_required
def export_students(fmt):
    q = request.args.get('q', '').strip()
    course = request.args.get('course', '').strip() or None
    year = _int_arg('year')
    low = request.args.get('low') == '1'
    back = _linker('admin_attendance.students', dict(q=q or None, course=course, year=year),
                   low='1' if low else None)()
    return _export(lambda: export_service.students_report(
        query=q or None, course_code=course, year=year, low_only=low), fmt, back)


@admin_attendance_bp.route('/export/student/<fmt>/<path:student_id>')
@login_required
@admin_required
def export_student(fmt, student_id):
    range_key, date_from, date_to = _resolve_range()
    back = url_for('admin_attendance.student_view', student_id=student_id,
                   **{k: v for k, v in dict(
                       range=range_key if range_key != 'custom' else None,
                       date_from=request.args.get('date_from') or None,
                       date_to=request.args.get('date_to') or None).items() if v})
    return _export(lambda: export_service.student_report(student_id, date_from, date_to),
                   fmt, back)


@admin_attendance_bp.route('/export/session/<fmt>/<int:session_id>')
@login_required
@admin_required
def export_session(fmt, session_id):
    back = url_for('admin_attendance.sheet', session_id=session_id)
    return _export(lambda: export_service.session_report(session_id), fmt, back,
                   pdf_allowed='session' in PDF_REPORTS)