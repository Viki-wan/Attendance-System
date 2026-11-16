"""
Student Admin Service
Admin-side student management: listing, registration (with face capture),
CRUD, and course enrollment. Face detection/encoding/duplicate-checking
logic lives entirely in FaceRecognitionService (one home for all things
face_recognition, same principle as Phase 2 keeping auth logic in
AuthService); account/enrollment lifecycle uses Student's own model
methods directly, the same way Phase 2 calls Class.assign_instructor()
directly rather than duplicating that logic here.
"""

from datetime import datetime
import logging

from app import db
from app.models import Student, Course, StudentCourse
from app.services.face_recognition_service import FaceRecognitionService
from app.utils.academic_calendar import get_current_semester
from config.constants import ActivityType, UserType

logger = logging.getLogger(__name__)


class StudentAdminService:
    """Service for admin management of student accounts, enrollment, and face registration."""

    def __init__(self):
        self.face_service = FaceRecognitionService()

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_students(self, search=None, status=None, has_face=None, page=1, per_page=20):
        """
        Paginated, searchable, filterable list of students.

        Args:
            search (str, optional): Matches student_id, name, email, or phone.
            status (str, optional): 'active' or 'inactive'. None = all.
            has_face (str, optional): 'yes' or 'no'. None = all.
            page (int): Page number, 1-indexed.
            per_page (int): Rows per page.

        Returns:
            Pagination: Flask-SQLAlchemy pagination object of Student rows.
        """
        query = Student.query

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                db.or_(
                    Student.student_id.ilike(pattern),
                    Student.fname.ilike(pattern),
                    Student.lname.ilike(pattern),
                    Student.email.ilike(pattern),
                    Student.phone.ilike(pattern),
                )
            )

        if status == 'active':
            query = query.filter(Student.is_active == True)
        elif status == 'inactive':
            query = query.filter(Student.is_active == False)

        if has_face == 'yes':
            query = query.filter(Student.face_encoding.isnot(None))
        elif has_face == 'no':
            query = query.filter(Student.face_encoding.is_(None))

        query = query.order_by(Student.student_id.asc())

        return query.paginate(page=page, per_page=per_page, error_out=False)

    def get_student(self, student_id):
        """Fetch a single student by ID, or None."""
        return Student.query.get(student_id)

    # ------------------------------------------------------------------
    # Registration (create + face)
    # ------------------------------------------------------------------

    def register_student(self, admin_username, student_id, fname, lname, image_data,
                          email=None, phone=None, course=None, year_of_study=1,
                          current_semester=None, force=False):
        """
        Register a new student: validates the captured face photo via
        FaceRecognitionService, creates the Student row, and enrolls them
        in their course for the given semester/year (if a course is given).

        Args:
            current_semester: Campus-wide semester to record (1 or 2). Defaults
                to today's campus semester (see utils/academic_calendar.py).
            force (bool): True when the operator confirmed "continue anyway"
                after a blurry-photo warning.

        Returns:
            tuple: (success: bool, message: str, student: Student or None,
                    needs_confirmation: bool)
            needs_confirmation is True only when the photo was flagged as
            blurry and has not been force-accepted yet.
        """
        if not student_id:
            return False, "Student ID is required", None, False

        if current_semester is None:
            current_semester = str(get_current_semester())

        if Student.query.get(student_id):
            return False, "A student with this ID already exists", None, False

        # Validate course before the (expensive) face processing step
        if course and not Course.query.get(course):
            return False, "Course not found", None, False

        face_result = self.face_service.register_student_face(image_data, student_id, force=force)

        if not face_result['success']:
            return (False, face_result['error'], None,
                    face_result.get('requires_confirmation', False))

        try:
            student = Student(
                student_id=student_id,
                fname=fname,
                lname=lname,
                email=email,
                phone=phone,
                course=course,
                year_of_study=year_of_study,
                current_semester=current_semester,
                image_path=face_result['image_path'],
                image_hash=face_result['image_hash'],
                face_encoding=face_result['face_encoding'],
                face_only_path=face_result['face_only_path'],
                face_encoding_path=face_result['encoding_path'],
                is_active=True
            )
            db.session.add(student)
            db.session.commit()

            if course:
                student.enroll_in_course(course, semester=current_semester, year=year_of_study)

            self._log_admin_activity(
                admin_username,
                ActivityType.STUDENT_REGISTERED,
                f"Registered student {student_id} ({fname} {lname}) with "
                f"{face_result['num_encodings']} face encodings"
            )

            return True, "Student registered successfully", student, False

        except Exception as e:
            db.session.rollback()
            logger.error(f"Student registration error: {str(e)}")
            return False, "Student registration failed", None, False

    def reregister_face(self, admin_username, student_id, image_data, force=False):
        """
        Re-capture an existing student's face photo (e.g. the original was
        poor quality, or their appearance changed significantly). Overwrites
        their stored image/hash/encoding.

        Args:
            force (bool): True when the operator confirmed "continue anyway"
                after a blurry-photo warning.

        Returns:
            tuple: (success: bool, message: str, needs_confirmation: bool)
        """
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found", False

        face_result = self.face_service.register_student_face(
            image_data, student_id, exclude_student_id=student_id, force=force
        )

        if not face_result['success']:
            return (False, face_result['error'],
                    face_result.get('requires_confirmation', False))

        try:
            student.image_path = face_result['image_path']
            student.image_hash = face_result['image_hash']
            student.face_encoding = face_result['face_encoding']
            student.face_only_path = face_result['face_only_path']
            student.face_encoding_path = face_result['encoding_path']
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.FACE_ENCODING_UPDATED,
                f"Re-registered face for student {student_id} "
                f"({face_result['num_encodings']} encodings)"
            )

            return True, "Face re-registered successfully", False

        except Exception as e:
            db.session.rollback()
            logger.error(f"Face re-registration error: {str(e)}")
            return False, "Face re-registration failed", False

    # ------------------------------------------------------------------
    # Profile updates
    # ------------------------------------------------------------------

    def update_student(self, admin_username, student_id, **kwargs):
        """
        Update student profile fields (fname, lname, email, phone, course,
        year_of_study). No photo involved. current_semester is campus-wide and not edited here.

        Returns:
            tuple: (success: bool, message: str)
        """
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found"

        allowed_fields = {'fname', 'lname', 'email', 'phone', 'course', 'year_of_study'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        try:
            for field, value in updates.items():
                setattr(student, field, value)
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.STUDENT_UPDATED,
                f"Updated student {student_id}: {', '.join(updates.keys())}"
            )

            return True, "Student updated successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Student update error: {str(e)}")
            return False, "Student update failed"

    # ------------------------------------------------------------------
    # Account lifecycle (Student's own model methods -- same pattern as
    # Phase 2 calling Class.assign_instructor()/remove_instructor() directly)
    # ------------------------------------------------------------------

    def deactivate_student(self, admin_username, student_id):
        """Deactivate a student account. Returns (success, message)."""
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found"

        student.deactivate()

        self._log_admin_activity(
            admin_username,
            ActivityType.ACCOUNT_DEACTIVATED,
            f"Deactivated student {student_id}"
        )

        return True, "Student deactivated"

    def activate_student(self, admin_username, student_id):
        """Reactivate a student account. Returns (success, message)."""
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found"

        student.activate()

        self._log_admin_activity(
            admin_username,
            ActivityType.ACCOUNT_ACTIVATED,
            f"Activated student {student_id}"
        )

        return True, "Student activated"

    # ------------------------------------------------------------------
    # Course enrollment (student_courses) -- reuses Student model helpers
    # ------------------------------------------------------------------

    def enroll_course(self, admin_username, student_id, course_code, semester=None, year=None,
                       enrollment_id=None):
        """
        Enroll a student in a course. Returns (success, message).

        If enrollment_id is given, that existing (dropped) enrollment row is
        reactivated as-is. This matters for rows created by the PyQt app,
        which have no year: matching on semester/year would miss them and
        create a duplicate instead.
        """
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found"

        if enrollment_id:
            enrollment = StudentCourse.query.get(enrollment_id)
            if not enrollment or enrollment.student_id != student_id:
                return False, "Enrollment not found"

            try:
                enrollment.reactivate()

                self._log_admin_activity(
                    admin_username,
                    ActivityType.PROFILE_UPDATED,
                    f"Re-enrolled student {student_id} in course {enrollment.course_code} "
                    f"({enrollment.semester}, {enrollment.year})"
                )

                return True, "Course re-enrolled"

            except Exception as e:
                db.session.rollback()
                logger.error(f"Course re-enrollment error: {str(e)}")
                return False, "Course re-enrollment failed"

        if not Course.query.get(course_code):
            return False, "Course not found"

        try:
            student.enroll_in_course(course_code, semester=semester, year=year)

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Enrolled student {student_id} in course {course_code} ({semester}, {year})"
            )

            return True, "Course enrollment successful"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Course enrollment error: {str(e)}")
            return False, "Course enrollment failed"

    def drop_course(self, admin_username, student_id, course_code, semester=None, year=None,
                     enrollment_id=None):
        """
        Drop a student's course enrollment. Returns (success, message).

        Prefers enrollment_id (exact row, works even when semester/year are
        empty, as in PyQt-created enrollments). Falls back to the model's
        semester/year matching when no id is given.
        """
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found"

        if enrollment_id:
            enrollment = StudentCourse.query.get(enrollment_id)
            if not enrollment or enrollment.student_id != student_id:
                return False, "Enrollment not found"
            course_code = enrollment.course_code
            enrollment.drop()
            dropped = True
        else:
            dropped = student.drop_course(course_code, semester=semester, year=year)

        if not dropped:
            return False, "Enrollment not found"

        self._log_admin_activity(
            admin_username,
            ActivityType.PROFILE_UPDATED,
            f"Dropped student {student_id} from course {course_code}"
        )

        return True, "Course dropped"

    # ------------------------------------------------------------------
    # Helpers for form dropdowns
    # ------------------------------------------------------------------

    def get_assignable_courses(self):
        """Active courses, for populating the 'enroll in course' dropdown."""
        return Course.get_active_courses()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_admin_activity(self, admin_username, activity_type, description):
        """Log an action under the admin's own identity (user_type='admin')."""
        try:
            from app.models.activity_log import ActivityLog

            log_entry = ActivityLog(
                user_id=admin_username,
                user_type=UserType.ADMIN,
                activity_type=activity_type,
                description=description,
                timestamp=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Admin activity logging error: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass