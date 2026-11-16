"""
Admin Course & Class Management Routes
Courses: list, create, view, edit, deactivate/activate, guarded delete.
Classes: list, create, view, edit, deactivate/activate, guarded delete,
and assigning/removing lecturers.

URL note: course codes and class IDs are always the LAST URL segment and use
the <path:...> converter. Class IDs contain a space ('COMP 101'), and the same
approach avoided the 404s that slashes in student IDs caused in Phase 3.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.course_admin_service import CourseAdminService

admin_courses_bp = Blueprint('admin_courses', __name__, url_prefix='/admin/courses')

service = CourseAdminService()

YEARS = [1, 2, 3, 4, 5, 6]
SEMESTERS = [1, 2]


# ----------------------------------------------------------------------
# Courses
# ----------------------------------------------------------------------

@admin_courses_bp.route('/')
@login_required
@admin_required
def index():
    """List courses with search, status filter, and pagination."""
    search = request.args.get('q', '').strip() or None
    status = request.args.get('status', '').strip() or None
    page = request.args.get('page', 1, type=int)

    pagination = service.list_courses(search=search, status=status, page=page, per_page=20)

    return render_template(
        'admin/courses/list.html',
        pagination=pagination,
        courses=pagination.items,
        search=search or '',
        status=status or ''
    )


@admin_courses_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Create a new course."""
    if request.method == 'POST':
        success, message, course = service.create_course(
            admin_username=current_user.username,
            course_code=request.form.get('course_code', ''),
            course_name=request.form.get('course_name', ''),
            faculty=request.form.get('faculty', '')
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_courses.view', course_code=course.course_code))

        flash(message, 'danger')
        return render_template('admin/courses/create.html', form_data=request.form)

    return render_template('admin/courses/create.html', form_data={})


@admin_courses_bp.route('/view/<path:course_code>')
@login_required
@admin_required
def view(course_code):
    """Course detail: stats and its classes grouped by year/semester."""
    course = service.get_course(course_code)

    if not course:
        flash('Course not found', 'danger')
        return redirect(url_for('admin_courses.index'))

    return render_template(
        'admin/courses/view.html',
        course=course,
        stats=service.get_course_stats(course),
        usage=service.get_course_usage(course),
        class_groups=service.get_course_class_groups(course)
    )


@admin_courses_bp.route('/edit/<path:course_code>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(course_code):
    """Edit a course's name and faculty."""
    course = service.get_course(course_code)

    if not course:
        flash('Course not found', 'danger')
        return redirect(url_for('admin_courses.index'))

    if request.method == 'POST':
        success, message = service.update_course(
            current_user.username,
            course_code,
            request.form.get('course_name', ''),
            request.form.get('faculty', '')
        )

        flash(message, 'success' if success else 'danger')

        if success:
            return redirect(url_for('admin_courses.view', course_code=course_code))

        return render_template('admin/courses/edit.html', course=course, form_data=request.form)

    return render_template('admin/courses/edit.html', course=course, form_data={})


@admin_courses_bp.route('/deactivate/<path:course_code>', methods=['POST'])
@login_required
@admin_required
def deactivate(course_code):
    """Deactivate (soft-delete) a course."""
    success, message = service.deactivate_course(current_user.username, course_code)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_courses.view', course_code=course_code))


@admin_courses_bp.route('/activate/<path:course_code>', methods=['POST'])
@login_required
@admin_required
def activate(course_code):
    """Reactivate a course."""
    success, message = service.activate_course(current_user.username, course_code)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_courses.view', course_code=course_code))


@admin_courses_bp.route('/delete/<path:course_code>', methods=['POST'])
@login_required
@admin_required
def delete(course_code):
    """Permanently delete a course (only if nothing uses it)."""
    success, message = service.delete_course(current_user.username, course_code)
    flash(message, 'success' if success else 'danger')

    if success:
        return redirect(url_for('admin_courses.index'))

    return redirect(url_for('admin_courses.view', course_code=course_code))


# ----------------------------------------------------------------------
# Classes
# ----------------------------------------------------------------------

@admin_courses_bp.route('/classes')
@login_required
@admin_required
def classes_index():
    """List classes across all courses with filters and pagination."""
    search = request.args.get('q', '').strip() or None
    course = request.args.get('course', '').strip() or None
    instructor = request.args.get('instructor', '').strip() or None
    status = request.args.get('status', '').strip() or None
    year = request.args.get('year', type=int)
    page = request.args.get('page', 1, type=int)

    pagination = service.list_classes(
        search=search, course_code=course, instructor_id=instructor,
        status=status, year=year, page=page, per_page=25
    )

    return render_template(
        'admin/courses/classes_list.html',
        pagination=pagination,
        classes=pagination.items,
        courses=service.get_all_courses(),
        instructors=service.get_filter_instructors(),
        years=YEARS,
        search=search or '',
        course=course or '',
        instructor=instructor or '',
        status=status or '',
        year=year or ''
    )


def _render_class_form(class_obj=None, form_data=None):
    return render_template(
        'admin/courses/class_form.html',
        class_obj=class_obj,
        form_data=form_data or {},
        courses=service.get_all_courses(),
        years=YEARS,
        semesters=SEMESTERS
    )


@admin_courses_bp.route('/classes/create', methods=['GET', 'POST'])
@login_required
@admin_required
def class_create():
    """Create a class. ?course=CODE pre-selects the course (used by the course page)."""
    if request.method == 'POST':
        success, message, class_obj = service.create_class(
            admin_username=current_user.username,
            class_id=request.form.get('class_id', ''),
            course_code=request.form.get('course_code', '').strip(),
            class_name=request.form.get('class_name', ''),
            year=request.form.get('year', type=int),
            semester=request.form.get('semester', type=int)
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_courses.class_view', class_id=class_obj.class_id))

        flash(message, 'danger')
        return _render_class_form(form_data=request.form)

    return _render_class_form(form_data={'course_code': request.args.get('course', '').strip()})


@admin_courses_bp.route('/classes/view/<path:class_id>')
@login_required
@admin_required
def class_view(class_id):
    """Class detail: lecturers, students, and usage."""
    class_obj = service.get_class(class_id)

    if not class_obj:
        flash('Class not found', 'danger')
        return redirect(url_for('admin_courses.classes_index'))

    students = service.get_class_students(class_obj)

    return render_template(
        'admin/courses/class_view.html',
        class_obj=class_obj,
        lecturers=class_obj.class_instructors.all(),
        assignable_instructors=service.get_assignable_instructors(class_obj),
        students=students,
        lecturer_panel_count=service.get_lecturer_panel_student_count(class_obj),
        usage=service.get_class_usage(class_obj)
    )


@admin_courses_bp.route('/classes/edit/<path:class_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def class_edit(class_id):
    """Edit a class's name, course, year, or semester."""
    class_obj = service.get_class(class_id)

    if not class_obj:
        flash('Class not found', 'danger')
        return redirect(url_for('admin_courses.classes_index'))

    if request.method == 'POST':
        success, message = service.update_class(
            current_user.username,
            class_id,
            class_name=request.form.get('class_name', ''),
            course_code=request.form.get('course_code', '').strip(),
            year=request.form.get('year', type=int),
            semester=request.form.get('semester', type=int)
        )

        flash(message, 'success' if success else 'danger')

        if success:
            return redirect(url_for('admin_courses.class_view', class_id=class_id))

        return _render_class_form(class_obj=class_obj, form_data=request.form)

    return _render_class_form(class_obj=class_obj)


@admin_courses_bp.route('/classes/deactivate/<path:class_id>', methods=['POST'])
@login_required
@admin_required
def class_deactivate(class_id):
    """Deactivate (soft-delete) a class."""
    success, message = service.deactivate_class(current_user.username, class_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_courses.class_view', class_id=class_id))


@admin_courses_bp.route('/classes/activate/<path:class_id>', methods=['POST'])
@login_required
@admin_required
def class_activate(class_id):
    """Reactivate a class."""
    success, message = service.activate_class(current_user.username, class_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_courses.class_view', class_id=class_id))


@admin_courses_bp.route('/classes/delete/<path:class_id>', methods=['POST'])
@login_required
@admin_required
def class_delete(class_id):
    """Permanently delete a class (only if it has no sessions or timetable entries)."""
    class_obj = service.get_class(class_id)
    course_code = class_obj.course_code if class_obj else None

    success, message = service.delete_class(current_user.username, class_id)
    flash(message, 'success' if success else 'danger')

    if success:
        if course_code:
            return redirect(url_for('admin_courses.view', course_code=course_code))
        return redirect(url_for('admin_courses.classes_index'))

    return redirect(url_for('admin_courses.class_view', class_id=class_id))


@admin_courses_bp.route('/classes/assign-instructor/<path:class_id>', methods=['POST'])
@login_required
@admin_required
def class_assign_instructor(class_id):
    """Assign a lecturer to a class."""
    instructor_id = request.form.get('instructor_id', '').strip()
    success, message = service.assign_instructor(current_user.username, class_id, instructor_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_courses.class_view', class_id=class_id))


@admin_courses_bp.route('/classes/remove-instructor/<instructor_id>/<path:class_id>', methods=['POST'])
@login_required
@admin_required
def class_remove_instructor(instructor_id, class_id):
    """Remove a lecturer from a class."""
    success, message = service.remove_instructor(current_user.username, class_id, instructor_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_courses.class_view', class_id=class_id))