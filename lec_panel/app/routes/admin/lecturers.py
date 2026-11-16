"""
Admin Lecturer Management Routes
List, create, edit, deactivate/activate, reset password,
and assign courses/classes to lecturers.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.lecturer_admin_service import LecturerAdminService

admin_lecturers_bp = Blueprint('admin_lecturers', __name__, url_prefix='/admin/lecturers')

service = LecturerAdminService()


@admin_lecturers_bp.route('/')
@login_required
@admin_required
def index():
    """List lecturers with search, status filter, and pagination."""
    search = request.args.get('q', '').strip() or None
    status = request.args.get('status', '').strip() or None
    page = request.args.get('page', 1, type=int)

    pagination = service.list_lecturers(search=search, status=status, page=page, per_page=20)

    return render_template(
        'admin/lecturers/list.html',
        pagination=pagination,
        lecturers=pagination.items,
        search=search or '',
        status=status or ''
    )


@admin_lecturers_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Create a new lecturer account."""
    if request.method == 'POST':
        instructor_id = request.form.get('instructor_id', '').strip()
        instructor_name = request.form.get('instructor_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        faculty = request.form.get('faculty', '').strip() or None

        success, message, instructor = service.create_lecturer(
            admin_username=current_user.username,
            instructor_id=instructor_id,
            instructor_name=instructor_name,
            phone=phone,
            email=email,
            faculty=faculty
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_lecturers.view', instructor_id=instructor.instructor_id))

        flash(message, 'danger')
        return render_template('admin/lecturers/create.html', form_data=request.form)

    return render_template('admin/lecturers/create.html', form_data={})


@admin_lecturers_bp.route('/<instructor_id>')
@login_required
@admin_required
def view(instructor_id):
    """Lecturer detail: profile, assigned courses, assigned classes."""
    lecturer = service.get_lecturer(instructor_id)

    if not lecturer:
        flash('Lecturer not found', 'danger')
        return redirect(url_for('admin_lecturers.index'))

    return render_template(
        'admin/lecturers/view.html',
        lecturer=lecturer,
        assigned_courses=lecturer.instructor_courses.all(),
        assigned_classes=lecturer.class_instructors.all(),
        available_courses=service.get_assignable_courses(),
        available_classes=service.get_assignable_classes()
    )


@admin_lecturers_bp.route('/<instructor_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(instructor_id):
    """Edit lecturer profile fields."""
    lecturer = service.get_lecturer(instructor_id)

    if not lecturer:
        flash('Lecturer not found', 'danger')
        return redirect(url_for('admin_lecturers.index'))

    if request.method == 'POST':
        updates = {
            'instructor_name': request.form.get('instructor_name', '').strip(),
            'email': request.form.get('email', '').strip() or None,
            'phone': request.form.get('phone', '').strip(),
            'faculty': request.form.get('faculty', '').strip() or None,
        }

        success, message = service.update_lecturer(
            current_user.username, instructor_id, **updates
        )

        flash(message, 'success' if success else 'danger')

        if success:
            return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))

        return render_template('admin/lecturers/edit.html', lecturer=lecturer)

    return render_template('admin/lecturers/edit.html', lecturer=lecturer)


@admin_lecturers_bp.route('/<instructor_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate(instructor_id):
    """Deactivate a lecturer account."""
    reason = request.form.get('reason', '').strip() or None
    success, message = service.deactivate_lecturer(current_user.username, instructor_id, reason)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))


@admin_lecturers_bp.route('/<instructor_id>/activate', methods=['POST'])
@login_required
@admin_required
def activate(instructor_id):
    """Reactivate a lecturer account."""
    success, message = service.activate_lecturer(current_user.username, instructor_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))


@admin_lecturers_bp.route('/<instructor_id>/reset-password', methods=['GET', 'POST'])
@login_required
@admin_required
def reset_password(instructor_id):
    """Admin-initiated password reset."""
    lecturer = service.get_lecturer(instructor_id)

    if not lecturer:
        flash('Lecturer not found', 'danger')
        return redirect(url_for('admin_lecturers.index'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('admin/lecturers/reset_password.html', lecturer=lecturer)

        success, message = service.reset_lecturer_password(
            current_user.username, instructor_id, new_password
        )

        flash(message, 'success' if success else 'danger')

        if success:
            return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))

    return render_template('admin/lecturers/reset_password.html', lecturer=lecturer)


@admin_lecturers_bp.route('/<instructor_id>/assign-course', methods=['POST'])
@login_required
@admin_required
def assign_course(instructor_id):
    """Assign lecturer to a course for a semester/year."""
    course_code = request.form.get('course_code', '').strip()
    semester = request.form.get('semester', '').strip()
    year = request.form.get('year', type=int)
    is_coordinator = request.form.get('is_coordinator') == 'on'

    success, message, _ = service.assign_course(
        current_user.username, instructor_id, course_code, semester, year, is_coordinator
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))


@admin_lecturers_bp.route('/<instructor_id>/remove-course/<int:assignment_id>', methods=['POST'])
@login_required
@admin_required
def remove_course(instructor_id, assignment_id):
    """Remove a course assignment."""
    success, message = service.remove_course_assignment(current_user.username, assignment_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))


@admin_lecturers_bp.route('/<instructor_id>/assign-class', methods=['POST'])
@login_required
@admin_required
def assign_class(instructor_id):
    """Assign lecturer to a class."""
    class_id = request.form.get('class_id', '').strip()
    success, message = service.assign_class(current_user.username, instructor_id, class_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))


@admin_lecturers_bp.route('/<instructor_id>/remove-class/<class_id>', methods=['POST'])
@login_required
@admin_required
def remove_class(instructor_id, class_id):
    """Remove a class assignment."""
    success, message = service.remove_class_assignment(current_user.username, instructor_id, class_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_lecturers.view', instructor_id=instructor_id))