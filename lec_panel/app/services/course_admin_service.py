"""
Course Admin Service
Admin-side management of courses and classes: listing, CRUD, soft delete
(activate/deactivate), guarded hard delete, and lecturer assignment to classes.

Conventions (match the live data and the lecturer panel):
- A class's `semester` is the campus-wide term, an integer 1 or 2
  (Sem 1 = Sep-Dec, Sem 2 = Jan-Apr). Every faculty shares the same calendar.
- A class's `year` is the cohort year (1-6). "Year level" 3.1 simply means
  year 3, semester 1 -- it is derived, not stored on the model.
- Instructor assignment reuses Class.assign_instructor()/remove_instructor(),
  the same model helpers Phase 2 uses from the lecturer side.
"""

from datetime import datetime
import logging
import re

from sqlalchemy import text

from app import db
from app.models import Course, Class, ClassInstructor, Instructor, Student, StudentCourse
from config.constants import ActivityType, UserType

logger = logging.getLogger(__name__)

# Same shape the PyQt class dialog accepted: 2-4 letters, optional space, 3 digits
CLASS_ID_PATTERN = re.compile(r'^([A-Za-z]{2,4})\s?([0-9]{3})$')
MAX_YEAR = 6
TERMS = (1, 2)


class CourseAdminService:
    """Service for admin management of courses, classes, and class lecturers."""

    # ------------------------------------------------------------------
    # Courses: listing
    # ------------------------------------------------------------------

    def list_courses(self, search=None, status=None, page=1, per_page=20):
        """
        Paginated, searchable, filterable list of courses.

        Args:
            search (str, optional): Matches code, name, or faculty.
            status (str, optional): 'active' or 'inactive'. None = all.

        Returns:
            Pagination: Flask-SQLAlchemy pagination of Course rows.
        """
        query = Course.query

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                db.or_(
                    Course.course_code.ilike(pattern),
                    Course.course_name.ilike(pattern),
                    Course.faculty.ilike(pattern),
                )
            )

        if status == 'active':
            query = query.filter(Course.is_active == True)
        elif status == 'inactive':
            query = query.filter(Course.is_active == False)

        return query.order_by(Course.course_code.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    def get_course(self, course_code):
        """Fetch a single course by code, or None."""
        return Course.query.get(course_code)

    def get_all_courses(self):
        """Every course (active or not), for filter/form dropdowns."""
        return Course.query.order_by(Course.course_code.asc()).all()

    # ------------------------------------------------------------------
    # Courses: CRUD
    # ------------------------------------------------------------------

    def create_course(self, admin_username, course_code, course_name, faculty=None):
        """
        Create a course.

        Returns:
            tuple: (success: bool, message: str, course: Course or None)
        """
        code, error = self._clean_code(course_code, 'Course code')
        if error:
            return False, error, None

        name, faculty, error = self._clean_course_fields(course_name, faculty)
        if error:
            return False, error, None

        if Course.query.get(code):
            return False, f"A course with the code '{code}' already exists", None

        try:
            course = Course(course_code=code, course_name=name, faculty=faculty, is_active=True)
            db.session.add(course)
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Created course {code} ({name})"
            )

            return True, "Course created successfully", course

        except Exception as e:
            db.session.rollback()
            logger.error(f"Course creation error: {str(e)}")
            return False, "Course creation failed", None

    def update_course(self, admin_username, course_code, course_name, faculty=None):
        """Update a course's name/faculty (the code is the primary key and cannot change)."""
        course = Course.query.get(course_code)
        if not course:
            return False, "Course not found"

        name, faculty, error = self._clean_course_fields(course_name, faculty)
        if error:
            return False, error

        try:
            course.course_name = name
            course.faculty = faculty
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Updated course {course_code}"
            )

            return True, "Course updated successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Course update error: {str(e)}")
            return False, "Course update failed"

    def deactivate_course(self, admin_username, course_code):
        """Soft-delete a course. Returns (success, message)."""
        course = Course.query.get(course_code)
        if not course:
            return False, "Course not found"

        course.deactivate()

        self._log_admin_activity(
            admin_username,
            ActivityType.ACCOUNT_DEACTIVATED,
            f"Deactivated course {course_code}"
        )

        return True, "Course deactivated"

    def activate_course(self, admin_username, course_code):
        """Reactivate a course. Returns (success, message)."""
        course = Course.query.get(course_code)
        if not course:
            return False, "Course not found"

        course.activate()

        self._log_admin_activity(
            admin_username,
            ActivityType.ACCOUNT_ACTIVATED,
            f"Activated course {course_code}"
        )

        return True, "Course activated"

    def get_course_usage(self, course):
        """
        What references this course. Hard delete is only safe when nothing
        does, because Course relationships cascade (classes, lecturer
        assignments, and student enrollments would all be deleted with it).
        """
        classes = Class.query.filter_by(course_code=course.course_code).count()
        instructors = course.instructor_courses.count()
        enrollments = course.student_courses.count()

        return {
            'classes': classes,
            'instructors': instructors,
            'enrollments': enrollments,
            'in_use': bool(classes or instructors or enrollments),
        }

    def delete_course(self, admin_username, course_code):
        """
        Permanently delete a course, only if nothing uses it (same rule as the
        PyQt app). Otherwise the admin should deactivate it instead.
        """
        course = Course.query.get(course_code)
        if not course:
            return False, "Course not found"

        usage = self.get_course_usage(course)
        if usage['in_use']:
            return False, (
                f"Cannot delete '{course.course_name}': it has {usage['classes']} class(es), "
                f"{usage['instructors']} lecturer assignment(s) and {usage['enrollments']} "
                f"student enrollment(s). Deactivate it instead."
            )

        try:
            name = course.course_name
            db.session.delete(course)
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Deleted course {course_code} ({name})"
            )

            return True, "Course deleted"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Course deletion error: {str(e)}")
            return False, "Course deletion failed"

    # ------------------------------------------------------------------
    # Course detail helpers
    # ------------------------------------------------------------------

    def get_course_stats(self, course):
        """Headline numbers for the course page."""
        code = course.course_code

        lecturers = (
            db.session.query(db.func.count(db.distinct(ClassInstructor.instructor_id)))
            .select_from(ClassInstructor)
            .join(Class, Class.class_id == ClassInstructor.class_id)
            .filter(Class.course_code == code)
            .scalar()
        ) or 0

        return {
            'classes_total': Class.query.filter_by(course_code=code).count(),
            'classes_active': Class.query.filter_by(course_code=code, is_active=True).count(),
            'lecturers': lecturers,
            'students': Student.query.filter_by(course=code, is_active=True).count(),
            'enrollments': course.student_courses.filter_by(status='Active').count(),
        }

    def get_course_class_groups(self, course):
        """
        The course's classes grouped by (year, semester), in order:
        [{'year': 1, 'semester': 1, 'classes': [Class, ...]}, ...]
        """
        classes = (
            Class.query.filter_by(course_code=course.course_code)
            .order_by(Class.year, Class.semester, Class.class_id)
            .all()
        )

        groups, index = [], {}
        for cls in classes:
            key = (cls.year, cls.semester)
            if key not in index:
                index[key] = {'year': cls.year, 'semester': cls.semester, 'classes': []}
                groups.append(index[key])
            index[key]['classes'].append(cls)

        return groups

    # ------------------------------------------------------------------
    # Classes: listing
    # ------------------------------------------------------------------

    def list_classes(self, search=None, course_code=None, instructor_id=None,
                     status=None, year=None, page=1, per_page=25):
        """
        Paginated, filterable list of classes across all courses.

        Args:
            search (str, optional): Matches class ID or name.
            course_code (str, optional): Only this course's classes.
            instructor_id (str, optional): Only classes this lecturer is assigned to.
            status (str, optional): 'active' or 'inactive'.
            year (int, optional): Cohort year.
        """
        query = Class.query

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                db.or_(Class.class_id.ilike(pattern), Class.class_name.ilike(pattern))
            )

        if course_code:
            query = query.filter(Class.course_code == course_code)

        if instructor_id:
            query = query.join(
                ClassInstructor, ClassInstructor.class_id == Class.class_id
            ).filter(ClassInstructor.instructor_id == instructor_id)

        if status == 'active':
            query = query.filter(Class.is_active == True)
        elif status == 'inactive':
            query = query.filter(Class.is_active == False)

        if year:
            query = query.filter(Class.year == year)

        query = query.order_by(Class.course_code, Class.year, Class.semester, Class.class_id)

        return query.paginate(page=page, per_page=per_page, error_out=False)

    def get_class(self, class_id):
        """Fetch a single class by ID, or None."""
        return Class.query.get(class_id)

    def get_filter_instructors(self):
        """All lecturers, for the class list's lecturer filter."""
        return Instructor.query.order_by(Instructor.instructor_name.asc()).all()

    # ------------------------------------------------------------------
    # Classes: CRUD
    # ------------------------------------------------------------------

    def create_class(self, admin_username, class_id, course_code, class_name, year, semester):
        """
        Create a class under a course.

        Args:
            class_id (str): e.g. 'COMP 101' (normalised to upper-case, one space).
            year (int): Cohort year, 1-6.
            semester (int): Campus-wide term, 1 or 2.

        Returns:
            tuple: (success: bool, message: str, class_obj: Class or None)
        """
        cid, error = self._normalize_class_id(class_id)
        if error:
            return False, error, None

        name, error = self._validate_class_fields(class_name, course_code, year, semester)
        if error:
            return False, error, None

        if Class.query.get(cid):
            return False, f"A class with the ID '{cid}' already exists", None

        try:
            class_obj = Class(
                class_id=cid,
                course_code=course_code,
                class_name=name,
                year=year,
                semester=semester,
                is_active=True
            )
            db.session.add(class_obj)
            db.session.commit()

            self._sync_legacy_columns(cid, course_code, year, semester)

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Created class {cid} ({name}) under {course_code}, year {year} semester {semester}"
            )

            return True, "Class created successfully", class_obj

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class creation error: {str(e)}")
            return False, "Class creation failed", None

    def update_class(self, admin_username, class_id, class_name, course_code, year, semester):
        """Update a class's name, course, year, or semester (the ID cannot change)."""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return False, "Class not found"

        name, error = self._validate_class_fields(class_name, course_code, year, semester)
        if error:
            return False, error

        try:
            class_obj.class_name = name
            class_obj.course_code = course_code
            class_obj.year = year
            class_obj.semester = semester
            db.session.commit()

            self._sync_legacy_columns(class_id, course_code, year, semester)

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Updated class {class_id}"
            )

            return True, "Class updated successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class update error: {str(e)}")
            return False, "Class update failed"

    def deactivate_class(self, admin_username, class_id):
        """Soft-delete a class. Returns (success, message)."""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return False, "Class not found"

        class_obj.deactivate()

        self._log_admin_activity(
            admin_username,
            ActivityType.ACCOUNT_DEACTIVATED,
            f"Deactivated class {class_id}"
        )

        return True, "Class deactivated"

    def activate_class(self, admin_username, class_id):
        """Reactivate a class. Returns (success, message)."""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return False, "Class not found"

        class_obj.activate()

        self._log_admin_activity(
            admin_username,
            ActivityType.ACCOUNT_ACTIVATED,
            f"Activated class {class_id}"
        )

        return True, "Class activated"

    def get_class_usage(self, class_obj):
        """Sessions and timetable entries tied to the class (both cascade on delete)."""
        sessions = class_obj.sessions.count()
        timetables = class_obj.timetables.count()

        return {
            'sessions': sessions,
            'timetables': timetables,
            'in_use': bool(sessions or timetables),
        }

    def delete_class(self, admin_username, class_id):
        """
        Permanently delete a class, only if it has no sessions (hence no
        attendance) and no timetable entries. Its lecturer assignments are
        removed with it. Otherwise the admin should deactivate it instead.
        """
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return False, "Class not found"

        usage = self.get_class_usage(class_obj)
        if usage['in_use']:
            return False, (
                f"Cannot delete '{class_obj.class_name}': it has {usage['sessions']} session(s) "
                f"and {usage['timetables']} timetable entr(ies). Deactivate it instead."
            )

        try:
            name = class_obj.class_name
            self._delete_class_course_links(class_id)
            db.session.delete(class_obj)  # cascades class_instructors
            db.session.commit()

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Deleted class {class_id} ({name})"
            )

            return True, "Class deleted"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class deletion error: {str(e)}")
            return False, "Class deletion failed"

    # ------------------------------------------------------------------
    # Class lecturers (class_instructors) -- reuses Class model helpers
    # ------------------------------------------------------------------

    def assign_instructor(self, admin_username, class_id, instructor_id):
        """Assign a lecturer to a class. Returns (success, message)."""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return False, "Class not found"

        instructor = Instructor.query.get(instructor_id)
        if not instructor:
            return False, "Lecturer not found"

        if class_obj.is_assigned_to(instructor_id):
            return False, "Lecturer is already assigned to this class"

        # Phase 5: the admin owns the timetable, so refuse an assignment that
        # would double-book the lecturer against their other classes.
        try:
            from app.services.timetable_admin_service import TimetableAdminService
            clashes = TimetableAdminService().check_lecturer_assignment(
                instructor_id, class_id
            )
        except Exception as e:
            logger.error(f"Timetable clash check failed during assignment: {str(e)}")
            clashes = []

        if clashes:
            shown = "; ".join(clashes[:3])
            extra = f" (and {len(clashes) - 3} more)" if len(clashes) > 3 else ""
            return False, (f"{instructor.instructor_name} can't be assigned: "
                           f"timetable clash - {shown}{extra}. "
                           "Adjust the timetable first.")

        try:
            class_obj.assign_instructor(instructor_id)

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Assigned lecturer {instructor_id} to class {class_id}"
            )

            return True, f"{instructor.instructor_name} assigned to {class_id}"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class lecturer assignment error: {str(e)}")
            return False, "Lecturer assignment failed"

    def remove_instructor(self, admin_username, class_id, instructor_id):
        """Remove a lecturer from a class. Returns (success, message)."""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return False, "Class not found"

        try:
            if not class_obj.remove_instructor(instructor_id):
                return False, "Lecturer was not assigned to this class"

            self._log_admin_activity(
                admin_username,
                ActivityType.PROFILE_UPDATED,
                f"Removed lecturer {instructor_id} from class {class_id}"
            )

            return True, "Lecturer removed from class"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Class lecturer removal error: {str(e)}")
            return False, "Failed to remove lecturer"

    def get_assignable_instructors(self, class_obj):
        """Active lecturers not yet assigned to the class, for the assign dropdown."""
        assigned_ids = [ci.instructor_id for ci in class_obj.class_instructors]

        query = Instructor.query.filter(Instructor.is_active == True)
        if assigned_ids:
            query = query.filter(~Instructor.instructor_id.in_(assigned_ids))

        return query.order_by(Instructor.instructor_name.asc()).all()

    # ------------------------------------------------------------------
    # Class detail helpers
    # ------------------------------------------------------------------

    def get_class_students(self, class_obj):
        """
        Active students of the class's course in the class's cohort year.

        The semester is campus-wide, so it plays no part in who belongs to a
        class. (Class.students, used by the lecturer panel, also requires the
        student's current_semester to equal the class semester -- see
        get_lecturer_panel_student_count for the comparison.)
        """
        return (
            Student.query.filter_by(
                course=class_obj.course_code,
                year_of_study=class_obj.year,
                is_active=True
            )
            .order_by(Student.student_id.asc())
            .all()
        )

    def get_lecturer_panel_student_count(self, class_obj):
        """The student count the lecturer panel itself uses for this class."""
        try:
            return class_obj.student_count
        except Exception as e:
            logger.warning(f"Could not compute lecturer-panel student count: {str(e)}")
            return None

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_code(value, label):
        """Upper-case a course code; reject blanks, spaces, and slashes (they break URLs)."""
        code = (value or '').strip().upper()

        if not code:
            return None, f"{label} is required"
        if len(code) > 20:
            return None, f"{label} must be 20 characters or fewer"
        if re.search(r'[\s/\\]', code):
            return None, f"{label} cannot contain spaces or slashes"

        return code, None

    @staticmethod
    def _clean_course_fields(course_name, faculty):
        """Validate course name/faculty. Returns (name, faculty, error)."""
        name = (course_name or '').strip()
        faculty = (faculty or '').strip() or None

        if not name:
            return None, None, "Course name is required"
        if len(name) > 200:
            return None, None, "Course name must be 200 characters or fewer"
        if faculty and len(faculty) > 100:
            return None, None, "Faculty must be 100 characters or fewer"

        return name, faculty, None

    @staticmethod
    def _normalize_class_id(value):
        """'comp101' / 'COMP 101' -> 'COMP 101'. Returns (class_id, error)."""
        match = CLASS_ID_PATTERN.match((value or '').strip())

        if not match:
            return None, "Class ID must look like 'COMP 101' (2-4 letters, then 3 digits)"

        prefix, digits = match.group(1).upper(), match.group(2)

        if digits[0] not in '123456':
            return None, "The first digit of the class number is the year (1-6)"

        return f"{prefix} {digits}", None

    @staticmethod
    def _validate_class_fields(class_name, course_code, year, semester):
        """Validate shared class fields. Returns (clean_name, error)."""
        name = (class_name or '').strip()

        if not name:
            return None, "Class name is required"
        if len(name) > 200:
            return None, "Class name must be 200 characters or fewer"
        if not course_code or not Course.query.get(course_code):
            return None, "Course not found"
        if year is None or not (1 <= year <= MAX_YEAR):
            return None, f"Year must be between 1 and {MAX_YEAR}"
        if semester not in TERMS:
            return None, "Semester must be 1 or 2"

        return name, None

    # ------------------------------------------------------------------
    # Legacy columns (not mapped by the Class model)
    # ------------------------------------------------------------------

    def _sync_legacy_columns(self, class_id, course_code, year, semester):
        """
        Keep two legacy structures in step, as the faker/PyQt-era data has them:
        - classes.year_level (e.g. 3.1 = year 3, semester 1)
        - the class_courses link row (class_id, course_code)
        Neither is read by the lecturer panel, and the Class model doesn't map
        them, so this is best-effort: a failure is logged, never raised.
        """
        try:
            db.session.execute(
                text("UPDATE classes SET year_level = :yl WHERE class_id = :cid"),
                {'yl': float(f"{year}.{semester}"), 'cid': class_id}
            )
            db.session.execute(
                text("DELETE FROM class_courses WHERE class_id = :cid"),
                {'cid': class_id}
            )
            db.session.execute(
                text("INSERT INTO class_courses (class_id, course_code) VALUES (:cid, :cc)"),
                {'cid': class_id, 'cc': course_code}
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Legacy column sync skipped for class {class_id}: {str(e)}")

    def _delete_class_course_links(self, class_id):
        """Remove the class_courses rows for a class about to be deleted (best-effort)."""
        try:
            db.session.execute(
                text("DELETE FROM class_courses WHERE class_id = :cid"),
                {'cid': class_id}
            )
        except Exception as e:
            logger.warning(f"class_courses cleanup skipped for class {class_id}: {str(e)}")

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