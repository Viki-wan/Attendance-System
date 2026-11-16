"""
Admin Student Management Routes
List, create (with webcam face registration), view, edit,
deactivate/activate, re-register face, and enroll/drop course
assignments for students.
"""

import os
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.student_admin_service import StudentAdminService
from app.utils.academic_calendar import get_current_semester
from config.config import Config

admin_students_bp = Blueprint('admin_students', __name__, url_prefix='/admin/students')

service = StudentAdminService()


@admin_students_bp.route('/')
@login_required
@admin_required
def index():
    """List students with search, status filter, face-registered filter, and pagination."""
    search = request.args.get('q', '').strip() or None
    status = request.args.get('status', '').strip() or None
    has_face = request.args.get('has_face', '').strip() or None
    page = request.args.get('page', 1, type=int)

    pagination = service.list_students(
        search=search, status=status, has_face=has_face, page=page, per_page=20
    )

    return render_template(
        'admin/students/list.html',
        pagination=pagination,
        students=pagination.items,
        search=search or '',
        status=status or '',
        has_face=has_face or ''
    )


@admin_students_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Register a new student, including webcam face capture."""

    def render_form(form_data, needs_confirmation=False):
        return render_template(
            'admin/students/create.html',
            form_data=form_data,
            available_courses=service.get_assignable_courses(),
            campus_semester=get_current_semester(),
            needs_confirmation=needs_confirmation
        )

    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        fname = request.form.get('fname', '').strip()
        lname = request.form.get('lname', '').strip()
        email = request.form.get('email', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        course = request.form.get('course', '').strip() or None
        year_of_study = request.form.get('year_of_study', 1, type=int)
        captured_image = request.form.get('captured_image', '').strip()
        force = request.form.get('force') == '1'

        if not captured_image:
            flash('Please capture a photo before submitting.', 'danger')
            return render_form(request.form)

        success, message, student, needs_confirmation = service.register_student(
            admin_username=current_user.username,
            student_id=student_id,
            fname=fname,
            lname=lname,
            image_data=captured_image,
            email=email,
            phone=phone,
            course=course,
            year_of_study=year_of_study,
            force=force
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_students.view', student_id=student.student_id))

        if needs_confirmation:
            # Blurry photo: re-render with the form and photo intact so the
            # operator can "continue anyway" (force=1) or retake.
            flash(message, 'warning')
            return render_form(request.form, needs_confirmation=True)

        flash(message, 'danger')
        return render_form(request.form)

    return render_form({})


@admin_students_bp.route('/view/<path:student_id>')
@login_required
@admin_required
def view(student_id):
    """Student profile: personal info, face status, course enrollments."""
    student = service.get_student(student_id)

    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('admin_students.index'))

    return render_template(
        'admin/students/view.html',
        student=student,
        enrollments=student.student_courses.all(),
        available_courses=service.get_assignable_courses(),
        campus_semester=get_current_semester()
    )


def _resolve_photo_file(stored_path):
    """
    Turn a path stored in the DB into an existing file, or None.

    Students registered in the PyQt app have RELATIVE paths (e.g.
    "student_images\\S11_10067_25.jpg") that only resolved from the project
    root, so relative paths are resolved against Config.BASE_DIR. As a last
    resort, look for the same file name in BASE_DIR/student_images.
    """
    if not stored_path:
        return None

    path = Path(stored_path)
    candidates = [path] if path.is_absolute() else [Path(Config.BASE_DIR) / path, path]
    candidates.append(Path(Config.BASE_DIR) / 'student_images' / path.name)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


@admin_students_bp.route('/photo/<path:student_id>')
@login_required
@admin_required
def photo(student_id):
    """Serve a student's stored face photo (admin only). Photos live outside /static."""
    student = service.get_student(student_id)

    if not student:
        abort(404)

    # ?full=1 -> full captured photo; default -> cropped face. Falls back to the other.
    if request.args.get('full') == '1':
        stored_paths = [student.image_path, student.face_only_path]
    else:
        stored_paths = [student.face_only_path, student.image_path]

    for stored in stored_paths:
        file_path = _resolve_photo_file(stored)
        if file_path:
            return send_file(file_path, mimetype='image/jpeg', max_age=0)

    abort(404)


@admin_students_bp.route('/edit/<path:student_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(student_id):
    """Edit student profile fields (no photo)."""
    student = service.get_student(student_id)

    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('admin_students.index'))

    if request.method == 'POST':
        updates = {
            'fname': request.form.get('fname', '').strip(),
            'lname': request.form.get('lname', '').strip(),
            'email': request.form.get('email', '').strip() or None,
            'phone': request.form.get('phone', '').strip() or None,
            'course': request.form.get('course', '').strip() or None,
            'year_of_study': request.form.get('year_of_study', type=int),
        }

        success, message = service.update_student(current_user.username, student_id, **updates)

        flash(message, 'success' if success else 'danger')

        if success:
            return redirect(url_for('admin_students.view', student_id=student_id))

        return render_template('admin/students/edit.html', student=student,
                                   available_courses=service.get_assignable_courses())

    return render_template('admin/students/edit.html', student=student,
                                   available_courses=service.get_assignable_courses())


@admin_students_bp.route('/deactivate/<path:student_id>', methods=['POST'])
@login_required
@admin_required
def deactivate(student_id):
    """Deactivate a student account."""
    success, message = service.deactivate_student(current_user.username, student_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_students.view', student_id=student_id))


@admin_students_bp.route('/activate/<path:student_id>', methods=['POST'])
@login_required
@admin_required
def activate(student_id):
    """Reactivate a student account."""
    success, message = service.activate_student(current_user.username, student_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_students.view', student_id=student_id))


@admin_students_bp.route('/register-face/<path:student_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def register_face(student_id):
    """Re-capture an existing student's face photo."""
    student = service.get_student(student_id)

    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('admin_students.index'))

    def render_form(form_data, needs_confirmation=False):
        return render_template(
            'admin/students/register_face.html',
            student=student,
            form_data=form_data,
            needs_confirmation=needs_confirmation
        )

    if request.method == 'POST':
        captured_image = request.form.get('captured_image', '').strip()
        force = request.form.get('force') == '1'

        if not captured_image:
            flash('Please capture a photo before submitting.', 'danger')
            return render_form(request.form)

        success, message, needs_confirmation = service.reregister_face(
            current_user.username, student_id, captured_image, force=force
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('admin_students.view', student_id=student_id))

        if needs_confirmation:
            flash(message, 'warning')
            return render_form(request.form, needs_confirmation=True)

        flash(message, 'danger')
        return render_form(request.form)

    return render_form({})


@admin_students_bp.route('/enroll-course/<path:student_id>', methods=['POST'])
@login_required
@admin_required
def enroll_course(student_id):
    """Enroll student in a course for a semester/year."""
    course_code = request.form.get('course_code', '').strip()
    semester = request.form.get('semester', '').strip() or None
    year = request.form.get('year', type=int)
    enrollment_id = request.form.get('enrollment_id', type=int)

    success, message = service.enroll_course(
        current_user.username, student_id, course_code, semester, year,
        enrollment_id=enrollment_id
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_students.view', student_id=student_id))


@admin_students_bp.route('/drop-course/<course_code>/<path:student_id>', methods=['POST'])
@login_required
@admin_required
def drop_course(student_id, course_code):
    """Drop a course enrollment."""
    semester = request.form.get('semester') or None
    year = request.form.get('year', type=int)
    enrollment_id = request.form.get('enrollment_id', type=int)

    success, message = service.drop_course(
        current_user.username, student_id, course_code, semester, year,
        enrollment_id=enrollment_id
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin_students.view', student_id=student_id))