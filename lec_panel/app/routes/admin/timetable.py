"""
Admin Timetable Routes
The admin owns the campus-wide master timetable (so clashes are prevented in
one place): entries with conflict detection, a clash audit, holidays, and bulk
session generation with a preview step.

URL note: timetable entry and holiday IDs are integers and are always the LAST
URL segment. Class IDs (which contain spaces) only ever travel as query-string
or form values here, never in the path.
"""

from datetime import date
from itertools import groupby

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.timetable_admin_service import (
    DAY_NAMES, DAY_ORDER, TimetableAdminService, group_by_day,
)
from app.utils.academic_calendar import get_current_semester

admin_timetable_bp = Blueprint('admin_timetable', __name__, url_prefix='/admin/timetable')

service = TimetableAdminService()

SEMESTERS = [1, 2]
YEARS = [1, 2, 3, 4, 5, 6]
DAYS = [(d, DAY_NAMES[d]) for d in DAY_ORDER]


def _int_arg(name):
    """Integer query argument or None (0 is a valid value, e.g. Sunday)."""
    raw = request.args.get(name, '').strip()
    return int(raw) if raw.lstrip('-').isdigit() else None


def _checked(name, default=False):
    """Checkbox state; a missing field means 'unchecked' once a form is posted."""
    if request.method == 'POST':
        return request.form.get(name) == '1'
    return default


# ----------------------------------------------------------------------
# Timetable: cohort overview, weekly calendar, list
# ----------------------------------------------------------------------

VIEWS = ('cohorts', 'week', 'list')


@admin_timetable_bp.route('/')
@login_required
@admin_required
def index():
    """
    Three ways to look at the timetable:

      cohorts - one card per course/year with clash and gap badges (the default
                until something is selected)
      week    - a time-of-day calendar for ONE cohort, lecturer or class
      list    - every matching entry, grouped by day

    Choosing a cohort, lecturer or class switches to the weekly calendar.
    """
    class_id = request.args.get('class_id', '').strip() or None
    sem_raw = request.args.get('semester', '').strip()

    # A class filter spans every semester unless one is chosen explicitly
    if sem_raw == 'all' or (class_id and not sem_raw):
        semester = None
    else:
        semester = int(sem_raw) if sem_raw.isdigit() else get_current_semester()

    course = request.args.get('course', '').strip() or None
    instructor = request.args.get('instructor', '').strip() or None
    year = _int_arg('year')
    day = _int_arg('day')
    status = request.args.get('status', 'active')
    if status not in ('active', 'inactive', 'all'):
        status = 'active'

    # The weekly calendar needs a scope, or every class piles into one grid
    scoped = bool(instructor or class_id or (course and year))
    view_param = request.args.get('view', '')
    view_param = view_param if view_param in VIEWS else ''
    view = view_param or ('week' if scoped else 'cohorts')

    hint = None
    if view == 'week' and not scoped:
        view = 'cohorts'
        hint = 'Pick a cohort below (or choose a lecturer or class) to see its week.'

    courses, instructors = service.get_filter_options()
    sem_arg = semester if semester else 'all'

    # Links that keep the current filters while switching view
    keep = dict(semester=sem_arg, course=course, year=year, instructor=instructor,
                day=day, class_id=class_id,
                status=status if status != 'active' else None)
    view_links = {
        v: url_for('admin_timetable.index', view=v, **keep) for v in VIEWS
    }

    context = dict(
        view=view, view_param=view_param, view_links=view_links, hint=hint,
        entries=[], days_shown=[], grid={}, cohort_groups=[], cohort_totals={},
        week=None, unscheduled=[], scope_label='',
        courses=courses, instructors=instructors,
        day_names=DAY_NAMES, days=DAYS, years=YEARS, semesters=SEMESTERS,
        today=date.today(), semester=sem_arg, course=course or '',
        instructor=instructor or '', year=year or '',
        day=day if day is not None else '', class_id=class_id or '', status=status,
        active_filters=bool(course or instructor or year or class_id
                            or day is not None or status != 'active'),
        more_open=bool(day is not None or status != 'active'),
    )

    if view == 'cohorts':
        cohorts = service.cohort_summary(semester=semester, course_code=course, year=year)
        for c in cohorts:
            c['url'] = url_for(
                'admin_timetable.index', view='week', semester=c['semester'],
                course=c['course_code'], year=c['year']
            )
        context['cohort_groups'] = [
            {'course_code': code, 'course_name': items[0]['course_name'], 'cohorts': items}
            for code, items in (
                (k, list(g)) for k, g in groupby(cohorts, key=lambda c: c['course_code'])
            )
        ]
        context['cohort_totals'] = {
            'cohorts': len(cohorts),
            'entries': sum(c['entry_count'] for c in cohorts),
            'clashes': sum(c['clashes'] for c in cohorts),
            'unscheduled': sum(c['unscheduled'] for c in cohorts),
            'expired': sum(c['expired'] for c in cohorts),
        }
        return render_template('admin/timetable/index.html', **context)

    entries = service.list_entries(
        semester=semester, course_code=course, year=year, instructor_id=instructor,
        day=day, class_id=class_id, status=status
    )
    context['entries'] = entries

    # Say what the calendar is showing
    parts = []
    if course and year:
        parts.append(f"{course} \u00b7 Year {year}")
    elif course:
        parts.append(course)
    elif year:
        parts.append(f"Year {year}")
    if instructor:
        name = next((i['instructor_name'] for i in instructors
                     if i['instructor_id'] == instructor), instructor)
        parts.append(name)
    if class_id:
        parts.append(f"Class {class_id}")
    parts.append(f"Semester {semester}" if semester else "All semesters")
    context['scope_label'] = ' \u00b7 '.join(parts)

    if view == 'week':
        context['week'] = service.week_layout(entries, semester=semester)
        context['unscheduled'] = service.classes_without_slot(
            semester=semester, course_code=course, year=year, instructor_id=instructor
        ) if not class_id else []
    else:
        context['days_shown'], context['grid'] = group_by_day(entries)

    return render_template('admin/timetable/index.html', **context)


# ----------------------------------------------------------------------
# Timetable: create / edit / actions
# ----------------------------------------------------------------------

def _render_entry_form(entry=None, form_data=None):
    defaults = service.window_defaults()
    semester = get_current_semester()
    return render_template(
        'admin/timetable/entry_form.html',
        entry=entry,
        form_data=form_data or {},
        classes=service.get_selectable_classes(),
        days=DAYS,
        windows=defaults,
        defaults={'effective_from': defaults[semester][0],
                  'effective_to': defaults[semester][1]}
    )


def _after_entry_redirect(class_id):
    return redirect(url_for('admin_timetable.index', class_id=class_id))


@admin_timetable_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Add a recurring slot. ?class_id=ID pre-selects the class."""
    if request.method == 'POST':
        success, message, _entry_id = service.create_entry(
            admin_username=current_user.username,
            class_id=request.form.get('class_id', ''),
            day_of_week=request.form.get('day_of_week'),
            start_time=request.form.get('start_time', ''),
            end_time=request.form.get('end_time', ''),
            effective_from=request.form.get('effective_from', ''),
            effective_to=request.form.get('effective_to', ''),
            generate_now=_checked('generate_now')
        )

        if success:
            flash(message, 'success')
            return _after_entry_redirect(request.form.get('class_id', '').strip())

        flash(message, 'danger')
        return _render_entry_form(form_data=request.form)

    class_id = request.args.get('class_id', '').strip()
    return _render_entry_form(form_data={'class_id': class_id} if class_id else {})


@admin_timetable_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(entry_id):
    """Edit a slot; changes can flow through to already-generated sessions."""
    entry = service.get_entry(entry_id)

    if not entry:
        flash('Timetable entry not found', 'danger')
        return redirect(url_for('admin_timetable.index'))

    if request.method == 'POST':
        success, message = service.update_entry(
            current_user.username, entry_id,
            day_of_week=request.form.get('day_of_week'),
            start_time=request.form.get('start_time', ''),
            end_time=request.form.get('end_time', ''),
            effective_from=request.form.get('effective_from', ''),
            effective_to=request.form.get('effective_to', ''),
            propagate=_checked('propagate')
        )

        if success:
            flash(message, 'success')
            return _after_entry_redirect(entry['class_id'])

        flash(message, 'danger')
        return _render_entry_form(entry=entry, form_data=request.form)

    return _render_entry_form(entry=entry)


@admin_timetable_bp.route('/deactivate/<int:entry_id>', methods=['POST'])
@login_required
@admin_required
def deactivate(entry_id):
    """Deactivate a slot, optionally removing its future untouched sessions."""
    success, message = service.deactivate_entry(
        current_user.username, entry_id, propagate=_checked('propagate')
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_timetable.edit', entry_id=entry_id))


@admin_timetable_bp.route('/activate/<int:entry_id>', methods=['POST'])
@login_required
@admin_required
def activate(entry_id):
    """Reactivate a slot (re-checks clashes)."""
    success, message = service.activate_entry(current_user.username, entry_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_timetable.edit', entry_id=entry_id))


@admin_timetable_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
@admin_required
def delete(entry_id):
    """Permanently delete a slot, optionally removing its future untouched sessions."""
    entry = service.get_entry(entry_id)
    class_id = entry['class_id'] if entry else None

    success, message = service.delete_entry(
        current_user.username, entry_id, propagate=_checked('propagate')
    )
    flash(message, 'success' if success else 'danger')

    if success and class_id:
        return _after_entry_redirect(class_id)
    if success:
        return redirect(url_for('admin_timetable.index'))
    return redirect(url_for('admin_timetable.edit', entry_id=entry_id))


@admin_timetable_bp.route('/check')
@login_required
@admin_required
def check():
    """Live clash check for the entry form (JSON)."""
    conflicts = service.check_slot(
        request.args.get('class_id', '').strip(),
        request.args.get('day_of_week'),
        request.args.get('start_time', ''),
        request.args.get('end_time', ''),
        request.args.get('effective_from', ''),
        request.args.get('effective_to', ''),
        exclude_id=request.args.get('exclude_id', type=int)
    )
    return jsonify({
        'conflicts': [{'kind': c['kind'], 'message': c['message']} for c in conflicts]
    })


# ----------------------------------------------------------------------
# Conflict audit
# ----------------------------------------------------------------------

@admin_timetable_bp.route('/conflicts')
@login_required
@admin_required
def conflicts():
    """Scan a semester's timetable for clashes and gaps."""
    semester = request.args.get('semester', type=int)
    if semester not in SEMESTERS:
        semester = get_current_semester()

    return render_template(
        'admin/timetable/conflicts.html',
        audit=service.audit(semester),
        semester=semester,
        semesters=SEMESTERS
    )


# ----------------------------------------------------------------------
# Holidays
# ----------------------------------------------------------------------

@admin_timetable_bp.route('/holidays')
@login_required
@admin_required
def holidays():
    """Holidays for a year, with add / edit / delete / copy-from-year."""
    years = service.holiday_years()
    year = request.args.get('year', type=int) or date.today().year

    return render_template(
        'admin/timetable/holidays.html',
        holidays=service.list_holidays(year),
        year=year,
        years=years
    )


@admin_timetable_bp.route('/holidays/create', methods=['POST'])
@login_required
@admin_required
def holiday_create():
    """Add a holiday."""
    holiday_date = request.form.get('date', '')
    success, message = service.create_holiday(
        current_user.username,
        name=request.form.get('name', ''),
        holiday_date=holiday_date,
        description=request.form.get('description', ''),
        is_recurring=request.form.get('is_recurring') == '1',
        remove_sessions=request.form.get('remove_sessions') == '1'
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_timetable.holidays', year=holiday_date[:4] or None))


@admin_timetable_bp.route('/holidays/edit/<int:holiday_id>', methods=['POST'])
@login_required
@admin_required
def holiday_edit(holiday_id):
    """Edit a holiday."""
    holiday_date = request.form.get('date', '')
    success, message = service.update_holiday(
        current_user.username, holiday_id,
        name=request.form.get('name', ''),
        holiday_date=holiday_date,
        description=request.form.get('description', ''),
        is_recurring=request.form.get('is_recurring') == '1',
        remove_sessions=request.form.get('remove_sessions') == '1'
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_timetable.holidays', year=holiday_date[:4] or None))


@admin_timetable_bp.route('/holidays/delete/<int:holiday_id>', methods=['POST'])
@login_required
@admin_required
def holiday_delete(holiday_id):
    """Delete a holiday."""
    year = request.form.get('year', type=int)
    success, message = service.delete_holiday(current_user.username, holiday_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_timetable.holidays', year=year))


@admin_timetable_bp.route('/holidays/copy', methods=['POST'])
@login_required
@admin_required
def holiday_copy():
    """Copy one-off holidays from one year to another."""
    from_year = request.form.get('from_year', type=int)
    to_year = request.form.get('to_year', type=int)

    if not from_year or not to_year:
        flash('Choose both years', 'danger')
        return redirect(url_for('admin_timetable.holidays'))

    success, message = service.copy_holidays(current_user.username, from_year, to_year)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_timetable.holidays', year=to_year if success else from_year))


# ----------------------------------------------------------------------
# Session generation (form -> preview -> run)
# ----------------------------------------------------------------------

def _generation_form():
    """The generation parameters as submitted (all strings / bools)."""
    scope = request.form.get('scope', 'all')
    return {
        'semester': request.form.get('semester', type=int),
        'scope': scope if scope in ('all', 'course', 'class') else 'all',
        'course_code': request.form.get('course_code', '').strip(),
        'class_id': request.form.get('class_id', '').strip(),
        'start_date': request.form.get('start_date', ''),
        'end_date': request.form.get('end_date', ''),
        'roll_expired': request.form.get('roll_expired') == '1',
    }


def _generation_kwargs(form):
    """Map the form onto the service's arguments, honouring the chosen scope."""
    return {
        'start_date': form['start_date'],
        'end_date': form['end_date'],
        'semester': form['semester'],
        'course_code': form['course_code'] if form['scope'] == 'course' else None,
        'class_id': form['class_id'] if form['scope'] == 'class' else None,
        'roll_expired': form['roll_expired'],
    }


def _render_generate(form, plan=None):
    courses, _ = service.get_filter_options()
    return render_template(
        'admin/timetable/generate.html',
        form=form,
        plan=plan,
        courses=courses,
        classes=service.get_selectable_classes(),
        semesters=SEMESTERS
    )


@admin_timetable_bp.route('/generate')
@login_required
@admin_required
def generate():
    """Generation form, pre-filled for the current semester."""
    defaults = service.generation_defaults()
    form = {
        'semester': defaults['semester'],
        'scope': 'all',
        'course_code': '',
        'class_id': '',
        'start_date': defaults['start_date'].isoformat(),
        'end_date': defaults['end_date'].isoformat(),
        'roll_expired': defaults['roll_expired'],
    }
    return _render_generate(form)


@admin_timetable_bp.route('/generate/preview', methods=['POST'])
@login_required
@admin_required
def generate_preview():
    """Show what generation would do. Nothing is written."""
    form = _generation_form()
    plan = service.plan_generation(**_generation_kwargs(form))

    if not plan['ok']:
        flash(plan['error'], 'danger')
        return _render_generate(form)

    return _render_generate(form, plan=plan)


@admin_timetable_bp.route('/generate/run', methods=['POST'])
@login_required
@admin_required
def generate_run():
    """Generate the sessions (the plan is recomputed, not trusted from the preview)."""
    form = _generation_form()
    success, message, plan = service.generate_sessions(
        current_user.username, **_generation_kwargs(form)
    )

    if success:
        flash(message, 'success')
        return redirect(url_for('admin_timetable.index'))

    flash(message, 'danger')
    return _render_generate(form)