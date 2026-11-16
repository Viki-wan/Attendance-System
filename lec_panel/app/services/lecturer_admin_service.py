"""
Lecturer Admin Service
Admin-side lecturer management: listing, CRUD, and course/class assignment.
Account lifecycle (create/deactivate/activate/reset password) is delegated
to AuthService so instructor-side auth logic has exactly one home.
"""

from datetime import datetime
import logging

from app import db
from app.models import Instructor, Course, Class, InstructorCourse, ClassInstructor
from app.services.auth_service import AuthService
from config.constants import ActivityType, UserType

logger = logging.getLogger(__name__)


class LecturerAdminService:
    """Service for admin management of lecturer accounts and assignments."""

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_lecturers(self, search=None, status=None, page=1, per_page=20):
        """
        Paginated, searchable, filterable list of lecturers.

        Args:
            search (str, optional): Matches name, email, or phone.
            status (str, optional): 'active' or 'inactive'. None = all.
            page (int): Page number, 1-indexed.
            per_page (int): Rows per page.

        Returns:
            Pagination: Flask-SQLAlchemy pagination object of Instructor rows.
        """
        query = Instructor.query

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                db.or_(
                    Instructor.instructor_name.ilike(pattern),
                    Instructor.email.ilike(pattern),
                    Instructor.phone.ilike(pattern),
                    Instructor.instructor_id.ilike(pattern),
                )
            )

        if status == 'active':
            query = query.filter(Instructor.is_active == 1)
        elif status == 'inactive':
            query = query.filter(Instructor.is_active == 0)

        query = query.order_by(Instructor.instructor_name.asc())

        return query.paginate(page=page, per_page=per_page, error_out=False)

    def get_lecturer(self, instructor_id):
        """Fetch a single lecturer by ID, or None."""
        return Instructor.query.get(instructor_id)

    # ------------------------------------------------------------------
    # Account lifecycle (delegates to AuthService)
    # ------------------------------------------------------------------

    def create_lecturer(self, admin_username, instructor_id, instructor_name, phone,
                         email=None, faculty=None):
        """
        Create a new lecturer account. Default password is the instructor_id;
        the lecturer is required to change it on first login.

        Returns:
            tuple: (success: bool, message: str, instructor: Instructor or None)
        """
        success, message, instructor = AuthService.create_instructor(
            instructor_id=instructor_id,
            instructor_name=instructor_name,
            phone=phone,
            email=email,
            faculty=faculty,
            created_by_admin=True
        )

        if success:
            self._log_admin_activity(
                admin_username,
                ActivityType.ACCOUNT_CREATED,
                f"Created lecturer {instructor_id} ({instructor_name})"
            )

        return success, message, instructor

    def update_lecturer(self, admin_username, instructor_id, **kwargs):
        """
        Update lecturer profile fields (instructor_name, email, phone, faculty).

        Returns:
            tuple: (success: bool, message: str)
        """
        success, message = AuthService.update_profile(instructor_id, **kwargs)

        if success:
            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Updated lecturer {instructor_id}: {', '.join(kwargs.keys())}"
            )

        return success, message

    def deactivate_lecturer(self, admin_username, instructor_id, reason=None):
        """Deactivate a lecturer account. Returns (success, message)."""
        success, message = AuthService.deactivate_account(instructor_id, reason=reason)

        if success:
            self._log_admin_activity(
                admin_username,
                ActivityType.ACCOUNT_DEACTIVATED,
                f"Deactivated lecturer {instructor_id}" + (f": {reason}" if reason else "")
            )

        return success, message

    def activate_lecturer(self, admin_username, instructor_id):
        """Reactivate a lecturer account. Returns (success, message)."""
        success, message = AuthService.activate_account(instructor_id)

        if success:
            self._log_admin_activity(
                admin_username,
                ActivityType.ACCOUNT_ACTIVATED,
                f"Activated lecturer {instructor_id}"
            )

        return success, message

    def reset_lecturer_password(self, admin_username, instructor_id, new_password):
        """
        Admin-initiated password reset (reuses AuthService.reset_password).
        Returns (success, message).
        """
        success, message = AuthService.reset_password(instructor_id, new_password)

        if success:
            self._log_admin_activity(
                admin_username,
                ActivityType.PASSWORD_RESET,
                f"Reset password for lecturer {instructor_id}"
            )

        return success, message

    # ------------------------------------------------------------------
    # Course assignment (instructor_courses)
    # ------------------------------------------------------------------

    def assign_course(self, admin_username, instructor_id, course_code, semester, year,
                       is_coordinator=False):
        """
        Assign a lecturer to teach a course for a given semester/year.

        Returns:
            tuple: (success: bool, message: str, assignment: InstructorCourse or None)
        """
        if not Instructor.query.get(instructor_id):
            return False, "Lecturer not found", None

        if not Course.query.get(course_code):
            return False, "Course not found", None

        existing = InstructorCourse.query.filter_by(
            instructor_id=instructor_id,
            course_code=course_code,
            semester=semester,
            year=year
        ).first()

        if existing:
            return False, "Lecturer is already assigned to this course for that semester/year", existing

        try:
            assignment = InstructorCourse(
                instructor_id=instructor_id,
                course_code=course_code,
                semester=semester,
                year=year,
                is_coordinator=bool(is_coordinator)
            )
            db.session.add(assignment)
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Assigned lecturer {instructor_id} to course {course_code} ({semester}, {year})"
            )

            return True, "Course assigned successfully", assignment

        except Exception as e:
            db.session.rollback()
            logger.error(f"Course assignment error: {str(e)}")
            return False, "Course assignment failed", None

    def remove_course_assignment(self, admin_username, assignment_id):
        """Remove a course assignment by its InstructorCourse row ID."""
        assignment = InstructorCourse.query.get(assignment_id)

        if not assignment:
            return False, "Assignment not found"

        try:
            instructor_id, course_code = assignment.instructor_id, assignment.course_code
            db.session.delete(assignment)
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Removed lecturer {instructor_id} from course {course_code}"
            )

            return True, "Course assignment removed"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Course assignment removal error: {str(e)}")
            return False, "Failed to remove course assignment"

    # ------------------------------------------------------------------
    # Class assignment (class_instructors) -- reuses Class model helpers
    # ------------------------------------------------------------------

    def assign_class(self, admin_username, instructor_id, class_id):
        """Assign a lecturer to a class. Returns (success, message)."""
        instructor = Instructor.query.get(instructor_id)
        class_obj = Class.query.get(class_id)

        if not instructor:
            return False, "Lecturer not found"
        if not class_obj:
            return False, "Class not found"

        if class_obj.is_assigned_to(instructor_id):
            return False, "Lecturer is already assigned to this class"

        try:
            class_obj.assign_instructor(instructor_id)

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Assigned lecturer {instructor_id} to class {class_id}"
            )

            return True, "Class assigned successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class assignment error: {str(e)}")
            return False, "Class assignment failed"

    def remove_class_assignment(self, admin_username, instructor_id, class_id):
        """Remove a lecturer's assignment to a class. Returns (success, message)."""
        class_obj = Class.query.get(class_id)

        if not class_obj:
            return False, "Class not found"

        try:
            removed = class_obj.remove_instructor(instructor_id)

            if not removed:
                return False, "Lecturer was not assigned to this class"

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Removed lecturer {instructor_id} from class {class_id}"
            )

            return True, "Class assignment removed"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class assignment removal error: {str(e)}")
            return False, "Failed to remove class assignment"

    # ------------------------------------------------------------------
    # Helpers for assignment form dropdowns
    # ------------------------------------------------------------------

    def get_assignable_courses(self):
        """Active courses, for populating the 'assign course' dropdown."""
        return Course.get_active_courses()

    def get_assignable_classes(self):
        """Active classes, for populating the 'assign class' dropdown."""
        return Class.get_active_classes()

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