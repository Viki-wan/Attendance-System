"""
API Classes Endpoints
Class management and roster information via API
"""
from flask import Blueprint, request, g
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import instructor_api_required, api_owns_resource
from app.middleware.rate_limiter import standard_rate_limit
from app.models.class_model import Class
from app.models.student import Student
from app.models.student_course import StudentCourse
from app.models.session import ClassSession
from app.models.class_instructor import ClassInstructor
from app.models.course import Course
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('api_classes', __name__, url_prefix='/api/v1/classes')


@bp.route('/', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_classes():
    """
    Get all classes assigned to the instructor
    
    Query Parameters:
        - course_code: Filter by course
        - year: Filter by year
        - semester: Filter by semester
        - is_active: Filter by active status (true/false)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)
    
    Returns:
        Paginated list of classes with student counts
    """
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Get instructor's class assignments
    assignments = ClassInstructor.query.filter_by(
        instructor_id=g.user_id
    ).all()
    
    class_ids = [a.class_id for a in assignments]
    
    if not class_ids:
        return APIResponse.success(
            data=[],
            message="No classes found (instructor not assigned to any classes)"
        )
    
    # Build query
    query = Class.query.filter(Class.class_id.in_(class_ids))
    
    # Filters
    course_code = request.args.get('course_code')
    if course_code:
        query = query.filter_by(course_code=course_code)
    
    year = request.args.get('year', type=int)
    if year:
        query = query.filter_by(year=year)
    
    semester = request.args.get('semester')
    if semester:
        query = query.filter_by(semester=semester)
    
    is_active = request.args.get('is_active')
    if is_active:
        is_active_bool = is_active.lower() == 'true'
        query = query.filter_by(is_active=is_active_bool)
    
    # Order by class name
    query = query.order_by(Class.class_name)
    
    # Get total count
    total = query.count()
    
    # Paginate
    classes = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    classes_data = []
    for class_obj in classes.items:
        # Get course details
        course = Course.query.get(class_obj.course_code)
        
        # Get student count
        student_count = StudentCourse.query.filter_by(
            course_code=class_obj.course_code,
            status='Active'
        ).count()
        
        # Get session counts
        total_sessions = ClassSession.query.filter_by(
            class_id=class_obj.class_id,
            created_by=g.user_id
        ).count()
        
        completed_sessions = ClassSession.query.filter_by(
            class_id=class_obj.class_id,
            created_by=g.user_id,
            status='completed'
        ).count()
        
        classes_data.append({
            'class_id': class_obj.class_id,
            'class_name': class_obj.class_name,
            'course_code': class_obj.course_code,
            'course_name': course.course_name if course else None,
            'faculty': course.faculty if course else None,
            'year': class_obj.year,
            'semester': class_obj.semester,
            'student_count': student_count,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'is_active': class_obj.is_active,
            'created_at': class_obj.created_at.isoformat() if class_obj.created_at else None
        })
    
    return APIResponse.paginated(
        data=classes_data,
        page=page,
        per_page=per_page,
        total=total,
        message="Classes retrieved successfully"
    )


@bp.route('/<string:class_id>', methods=['GET'])
@api_owns_resource('class')
@standard_rate_limit
def get_class(class_id):
    """
    Get detailed class information
    
    Returns:
        Class details including course info and statistics
    """
    class_obj = g.resource
    
    # Get course details
    course = Course.query.get(class_obj.course_code)
    
    # Get student count
    student_count = StudentCourse.query.filter_by(
        course_code=class_obj.course_code,
        status='Active'
    ).count()
    
    # Get session statistics
    total_sessions = ClassSession.query.filter_by(
        class_id=class_id,
        created_by=g.user_id
    ).count()
    
    completed_sessions = ClassSession.query.filter_by(
        class_id=class_id,
        created_by=g.user_id,
        status='completed'
    ).count()
    
    ongoing_sessions = ClassSession.query.filter_by(
        class_id=class_id,
        created_by=g.user_id,
        status='ongoing'
    ).count()
    
    scheduled_sessions = ClassSession.query.filter_by(
        class_id=class_id,
        created_by=g.user_id,
        status='scheduled'
    ).count()
    
    # Get average attendance for completed sessions
    avg_attendance = db.session.query(
        func.avg(ClassSession.attendance_count * 100.0 / ClassSession.total_students)
    ).filter(
        ClassSession.class_id == class_id,
        ClassSession.created_by == g.user_id,
        ClassSession.status == 'completed',
        ClassSession.total_students > 0
    ).scalar() or 0
    
    # Get instructor assignment date
    assignment = ClassInstructor.query.filter_by(
        class_id=class_id,
        instructor_id=g.user_id
    ).first()
    
    class_data = {
        'class_id': class_obj.class_id,
        'class_name': class_obj.class_name,
        'course_code': class_obj.course_code,
        'course_name': course.course_name if course else None,
        'faculty': course.faculty if course else None,
        'year': class_obj.year,
        'semester': class_obj.semester,
        'is_active': class_obj.is_active,
        'created_at': class_obj.created_at.isoformat() if class_obj.created_at else None,
        'assigned_date': assignment.assigned_date.isoformat() if assignment and assignment.assigned_date else None,
        'statistics': {
            'student_count': student_count,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'ongoing_sessions': ongoing_sessions,
            'scheduled_sessions': scheduled_sessions,
            'average_attendance': round(avg_attendance, 2)
        }
    }
    
    return APIResponse.success(
        data=class_data,
        message="Class retrieved successfully"
    )


@bp.route('/<string:class_id>/students', methods=['GET'])
@api_owns_resource('class')
@standard_rate_limit
def get_class_roster(class_id):
    """
    Get class roster (list of enrolled students)
    
    Query Parameters:
        - include_statistics: Include attendance statistics (true/false)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 50, max: 200)
    
    Returns:
        Paginated list of students in the class
    """
    class_obj = g.resource
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    include_statistics = request.args.get('include_statistics', 'false').lower() == 'true'
    
    # Get enrolled students
    query = db.session.query(Student).join(
        StudentCourse,
        Student.student_id == StudentCourse.student_id
    ).filter(
        StudentCourse.course_code == class_obj.course_code,
        StudentCourse.status == 'Active'
    ).order_by(Student.fname, Student.lname)
    
    # Get total count
    total = query.count()
    
    # Paginate
    students = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    roster_data = []
    for student in students.items:
        student_data = {
            'student_id': student.student_id,
            'first_name': student.fname,
            'last_name': student.lname,
            'full_name': f"{student.fname} {student.lname}",
            'email': student.email,
            'phone': student.phone,
            'year_of_study': student.year_of_study,
            'current_semester': student.current_semester,
            'has_face_encoding': student.face_encoding is not None
        }
        
        # Include attendance statistics if requested
        if include_statistics:
            # Get sessions for this class
            sessions = ClassSession.query.filter_by(
                class_id=class_id,
                created_by=g.user_id,
                status='completed'
            ).all()
            
            session_ids = [s.session_id for s in sessions]
            
            if session_ids:
                # Count attendance
                from app.models.attendance import Attendance
                present_count = Attendance.query.filter(
                    Attendance.student_id == student.student_id,
                    Attendance.session_id.in_(session_ids),
                    Attendance.status.in_(['Present', 'Late'])
                ).count()
                
                attendance_percentage = round((present_count / len(sessions) * 100), 2) if sessions else 0
            else:
                present_count = 0
                attendance_percentage = 0
            
            student_data['statistics'] = {
                'total_sessions': len(sessions),
                'sessions_attended': present_count,
                'attendance_percentage': attendance_percentage
            }
        
        roster_data.append(student_data)
    
    return APIResponse.paginated(
        data=roster_data,
        page=page,
        per_page=per_page,
        total=total,
        message="Class roster retrieved successfully"
    )


@bp.route('/<string:class_id>/sessions', methods=['GET'])
@api_owns_resource('class')
@standard_rate_limit
def get_class_sessions(class_id):
    """
    Get all sessions for a specific class
    
    Query Parameters:
        - status: Filter by status
        - date_from: Filter from date (YYYY-MM-DD)
        - date_to: Filter to date (YYYY-MM-DD)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)
    
    Returns:
        Paginated list of sessions for the class
    """
    class_obj = g.resource
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Build query
    query = ClassSession.query.filter_by(
        class_id=class_id,
        created_by=g.user_id
    )
    
    # Filters
    status = request.args.get('status')
    if status:
        if status not in ['scheduled', 'ongoing', 'completed', 'cancelled', 'dismissed']:
            return APIResponse.validation_error({'status': 'Invalid status value'})
        query = query.filter_by(status=status)
    
    date_from = request.args.get('date_from')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(ClassSession.date >= date_from_obj)
        except ValueError:
            return APIResponse.validation_error({'date_from': 'Invalid date format'})
    
    date_to = request.args.get('date_to')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(ClassSession.date <= date_to_obj)
        except ValueError:
            return APIResponse.validation_error({'date_to': 'Invalid date format'})
    
    # Order by date descending
    query = query.order_by(ClassSession.date.desc())
    
    # Get total count
    total = query.count()
    
    # Paginate
    sessions = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    sessions_data = []
    for session in sessions.items:
        sessions_data.append({
            'session_id': session.session_id,
            'class_id': session.class_id,
            'class_name': class_obj.class_name,
            'date': session.date.isoformat() if isinstance(session.date, datetime) else session.date,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'status': session.status,
            'attendance_count': session.attendance_count,
            'total_students': session.total_students,
            'attendance_percentage': round((session.attendance_count / session.total_students * 100), 2) if session.total_students > 0 else 0,
            'session_notes': session.session_notes,
            'created_at': session.created_at.isoformat() if session.created_at else None
        })
    
    return APIResponse.paginated(
        data=sessions_data,
        page=page,
        per_page=per_page,
        total=total,
        message="Class sessions retrieved successfully"
    )


@bp.route('/<string:class_id>/statistics', methods=['GET'])
@api_owns_resource('class')
@standard_rate_limit
def get_class_statistics(class_id):
    """
    Get comprehensive statistics for a class
    
    Query Parameters:
        - days: Number of days to include (default: 30)
    
    Returns:
        Class statistics including attendance trends
    """
    class_obj = g.resource
    days = request.args.get('days', 30, type=int)
    
    date_from = datetime.now().date() - timedelta(days=days)
    
    # Session statistics
    total_sessions = ClassSession.query.filter(
        ClassSession.class_id == class_id,
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from
    ).count()
    
    completed_sessions = ClassSession.query.filter(
        ClassSession.class_id == class_id,
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.status == 'completed'
    ).count()
    
    # Average attendance
    avg_attendance = db.session.query(
        func.avg(ClassSession.attendance_count * 100.0 / ClassSession.total_students)
    ).filter(
        ClassSession.class_id == class_id,
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.status == 'completed',
        ClassSession.total_students > 0
    ).scalar() or 0
    
    # Student count
    student_count = StudentCourse.query.filter_by(
        course_code=class_obj.course_code,
        status='Active'
    ).count()
    
    # Low attendance students (below 75%)
    sessions = ClassSession.query.filter(
        ClassSession.class_id == class_id,
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.status == 'completed'
    ).all()
    
    session_ids = [s.session_id for s in sessions]
    
    low_attendance_count = 0
    if session_ids and len(sessions) > 0:
        from app.models.attendance import Attendance
        
        # Get students enrolled in this course
        enrolled_students = db.session.query(StudentCourse.student_id).filter_by(
            course_code=class_obj.course_code,
            status='Active'
        ).all()
        
        for (student_id,) in enrolled_students:
            attended = Attendance.query.filter(
                Attendance.student_id == student_id,
                Attendance.session_id.in_(session_ids),
                Attendance.status.in_(['Present', 'Late'])
            ).count()
            
            percentage = (attended / len(sessions) * 100) if len(sessions) > 0 else 0
            
            if percentage < 75:
                low_attendance_count += 1
    
    stats_data = {
        'class_id': class_id,
        'class_name': class_obj.class_name,
        'course_code': class_obj.course_code,
        'period_days': days,
        'date_from': date_from.isoformat(),
        'date_to': datetime.now().date().isoformat(),
        'student_count': student_count,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'completion_rate': round((completed_sessions / total_sessions * 100), 2) if total_sessions > 0 else 0,
        'average_attendance': round(avg_attendance, 2),
        'low_attendance_students': low_attendance_count
    }
    
    return APIResponse.success(
        data=stats_data,
        message="Class statistics retrieved successfully"
    )