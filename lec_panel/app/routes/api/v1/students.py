"""
API Students Endpoints
Student data and attendance history via API
"""
from flask import Blueprint, request, g
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import instructor_api_required
from app.middleware.rate_limiter import standard_rate_limit
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.session import ClassSession
from app.models.class_model import Class
from app.models.student_course import StudentCourse
from app.models.activity_log import ActivityLog
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, and_

bp = Blueprint('api_students', __name__, url_prefix='/api/v1/students')


@bp.route('/', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_students():
    """
    Get students accessible to the instructor
    
    Query Parameters:
        - class_id: Filter by class (instructor must be assigned)
        - course_code: Filter by course
        - year_of_study: Filter by year
        - semester: Filter by semester
        - search: Search by name, ID, or email
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)
    
    Returns:
        Paginated list of students
    """
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Get instructor's classes
    from app.models.class_instructor import ClassInstructor
    instructor_classes = ClassInstructor.query.filter_by(
        instructor_id=g.user_id
    ).all()
    
    class_ids = [ic.class_id for ic in instructor_classes]
    
    if not class_ids:
        return APIResponse.success(
            data=[],
            message="No students found (instructor not assigned to any classes)"
        )
    
    # Get course codes from classes
    classes = Class.query.filter(Class.class_id.in_(class_ids)).all()
    course_codes = list(set([c.course_code for c in classes]))
    
    # Build query - students enrolled in instructor's courses
    query = db.session.query(Student).join(
        StudentCourse,
        Student.student_id == StudentCourse.student_id
    ).filter(
        StudentCourse.course_code.in_(course_codes),
        StudentCourse.status == 'Active'
    ).distinct()
    
    # Filters
    class_id = request.args.get('class_id')
    if class_id:
        # Verify instructor owns this class
        if class_id not in class_ids:
            return APIResponse.forbidden("You are not assigned to this class")
        
        class_obj = Class.query.get(class_id)
        if class_obj:
            query = query.filter(StudentCourse.course_code == class_obj.course_code)
    
    course_code = request.args.get('course_code')
    if course_code:
        query = query.filter(StudentCourse.course_code == course_code)
    
    year_of_study = request.args.get('year_of_study', type=int)
    if year_of_study:
        query = query.filter(Student.year_of_study == year_of_study)
    
    semester = request.args.get('semester')
    if semester:
        query = query.filter(Student.current_semester == semester)
    
    # Search
    search = request.args.get('search')
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Student.student_id.like(search_pattern),
                Student.fname.like(search_pattern),
                Student.lname.like(search_pattern),
                Student.email.like(search_pattern)
            )
        )
    
    # Order by name
    query = query.order_by(Student.fname, Student.lname)
    
    # Get total count
    total = query.count()
    
    # Paginate
    students = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    students_data = []
    for student in students.items:
        # Get enrollment info
        enrollment = StudentCourse.query.filter_by(
            student_id=student.student_id,
            status='Active'
        ).first()
        
        students_data.append({
            'student_id': student.student_id,
            'name': f"{student.fname} {student.lname}",
            'first_name': student.fname,
            'last_name': student.lname,
            'email': student.email,
            'phone': student.phone,
            'year_of_study': student.year_of_study,
            'current_semester': student.current_semester,
            'course': enrollment.course_code if enrollment else None,
            'is_active': student.is_active,
            'has_face_encoding': student.face_encoding is not None
        })
    
    return APIResponse.paginated(
        data=students_data,
        page=page,
        per_page=per_page,
        total=total,
        message="Students retrieved successfully"
    )


@bp.route('/<string:student_id>', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_student(student_id):
    """
    Get student details
    
    Returns:
        Student details including enrollment information
    """
    student = Student.query.get(student_id)
    
    if not student:
        return APIResponse.not_found("Student")
    
    # Verify instructor has access to this student
    from app.models.class_instructor import ClassInstructor
    instructor_classes = ClassInstructor.query.filter_by(
        instructor_id=g.user_id
    ).all()
    class_ids = [ic.class_id for ic in instructor_classes]
    classes = Class.query.filter(Class.class_id.in_(class_ids)).all()
    course_codes = [c.course_code for c in classes]
    
    # Check if student is enrolled in any of instructor's courses
    enrollment = StudentCourse.query.filter(
        StudentCourse.student_id == student_id,
        StudentCourse.course_code.in_(course_codes)
    ).first()
    
    if not enrollment:
        return APIResponse.forbidden("You don't have access to this student")
    
    # Get all enrollments
    enrollments = StudentCourse.query.filter_by(student_id=student_id).all()
    
    enrollment_data = []
    for enroll in enrollments:
        enrollment_data.append({
            'course_code': enroll.course_code,
            'semester': enroll.semester,
            'year': enroll.year,
            'status': enroll.status,
            'enrollment_date': enroll.enrollment_date
        })
    
    student_data = {
        'student_id': student.student_id,
        'first_name': student.fname,
        'last_name': student.lname,
        'full_name': f"{student.fname} {student.lname}",
        'email': student.email,
        'phone': student.phone,
        'year_of_study': student.year_of_study,
        'current_semester': student.current_semester,
        'is_active': student.is_active,
        'has_face_encoding': student.face_encoding is not None,
        'created_at': student.created_at.isoformat() if student.created_at else None,
        'enrollments': enrollment_data
    }
    
    return APIResponse.success(
        data=student_data,
        message="Student retrieved successfully"
    )


@bp.route('/<string:student_id>/attendance', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_student_attendance_history(student_id):
    """
    Get student's attendance history
    
    Query Parameters:
        - date_from: Filter from date (YYYY-MM-DD)
        - date_to: Filter to date (YYYY-MM-DD)
        - class_id: Filter by class
        - status: Filter by status
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)
    
    Returns:
        Paginated attendance history with session details
    """
    student = Student.query.get(student_id)
    
    if not student:
        return APIResponse.not_found("Student")
    
    # Verify access
    from app.models.class_instructor import ClassInstructor
    instructor_classes = ClassInstructor.query.filter_by(
        instructor_id=g.user_id
    ).all()
    class_ids = [ic.class_id for ic in instructor_classes]
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Build query - only sessions owned by instructor
    query = db.session.query(Attendance).join(
        ClassSession,
        Attendance.session_id == ClassSession.session_id
    ).filter(
        Attendance.student_id == student_id,
        ClassSession.created_by == g.user_id
    )
    
    # Filters
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
    
    class_id = request.args.get('class_id')
    if class_id:
        query = query.filter(ClassSession.class_id == class_id)
    
    status = request.args.get('status')
    if status:
        if status not in ['Present', 'Absent', 'Late', 'Excused']:
            return APIResponse.validation_error({'status': 'Invalid status value'})
        query = query.filter(Attendance.status == status)
    
    # Order by date descending
    query = query.order_by(ClassSession.date.desc())
    
    # Get total count
    total = query.count()
    
    # Paginate
    attendance_records = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    attendance_data = []
    for record in attendance_records.items:
        session = ClassSession.query.get(record.session_id)
        class_obj = Class.query.get(session.class_id) if session else None
        
        attendance_data.append({
            'id': record.id,
            'session_id': record.session_id,
            'class_id': session.class_id if session else None,
            'class_name': class_obj.class_name if class_obj else None,
            'course_code': class_obj.course_code if class_obj else None,
            'date': session.date.isoformat() if session and isinstance(session.date, datetime) else session.date if session else None,
            'start_time': session.start_time if session else None,
            'end_time': session.end_time if session else None,
            'status': record.status,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None,
            'method': record.method,
            'confidence_score': record.confidence_score,
            'notes': record.notes
        })
    
    return APIResponse.paginated(
        data=attendance_data,
        page=page,
        per_page=per_page,
        total=total,
        message="Attendance history retrieved successfully"
    )


@bp.route('/<string:student_id>/statistics', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_student_statistics(student_id):
    """
    Get student attendance statistics
    
    Query Parameters:
        - days: Number of days to include (default: 30)
        - class_id: Filter by specific class
    
    Returns:
        Attendance statistics for the student
    """
    student = Student.query.get(student_id)
    
    if not student:
        return APIResponse.not_found("Student")
    
    days = request.args.get('days', 30, type=int)
    class_id = request.args.get('class_id')
    
    date_from = datetime.now().date() - timedelta(days=days)
    
    # Build query for sessions in the period
    session_query = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.status == 'completed'
    )
    
    if class_id:
        session_query = session_query.filter_by(class_id=class_id)
    
    total_sessions = session_query.count()
    session_ids = [s.session_id for s in session_query.all()]
    
    # Get attendance records
    if session_ids:
        attendance_query = Attendance.query.filter(
            Attendance.student_id == student_id,
            Attendance.session_id.in_(session_ids)
        )
        
        # Status counts
        status_counts = db.session.query(
            Attendance.status,
            func.count(Attendance.id)
        ).filter(
            Attendance.student_id == student_id,
            Attendance.session_id.in_(session_ids)
        ).group_by(Attendance.status).all()
        
        counts = {
            'Present': 0,
            'Absent': 0,
            'Late': 0,
            'Excused': 0
        }
        
        for status, count in status_counts:
            counts[status] = count
        
        total_attended = counts['Present'] + counts['Late']
        
    else:
        counts = {'Present': 0, 'Absent': 0, 'Late': 0, 'Excused': 0}
        total_attended = 0
    
    attendance_percentage = round((total_attended / total_sessions * 100), 2) if total_sessions > 0 else 0
    
    # Determine risk level
    if attendance_percentage < 50:
        risk_level = 'Critical'
    elif attendance_percentage < 65:
        risk_level = 'High'
    elif attendance_percentage < 75:
        risk_level = 'Medium'
    else:
        risk_level = 'Low'
    
    stats_data = {
        'student_id': student_id,
        'student_name': f"{student.fname} {student.lname}",
        'period_days': days,
        'date_from': date_from.isoformat(),
        'date_to': datetime.now().date().isoformat(),
        'total_sessions': total_sessions,
        'present_count': counts['Present'],
        'absent_count': counts['Absent'],
        'late_count': counts['Late'],
        'excused_count': counts['Excused'],
        'total_attended': total_attended,
        'attendance_percentage': attendance_percentage,
        'risk_level': risk_level
    }
    
    return APIResponse.success(
        data=stats_data,
        message="Student statistics retrieved successfully"
    )


@bp.route('/import', methods=['POST'])
@instructor_api_required
@standard_rate_limit
def import_students():
    """
    Bulk import students (CSV data)
    
    Request Body:
        {
            "students": [
                {
                    "student_id": "string",
                    "first_name": "string",
                    "last_name": "string",
                    "email": "string",
                    "phone": "string",
                    "course_code": "string",
                    "year_of_study": int,
                    "semester": "string"
                },
                ...
            ]
        }
    
    Returns:
        Summary of import operation
    """
    data = request.get_json()
    
    if not data or 'students' not in data:
        return APIResponse.error("students array is required", status_code=400)
    
    students_data = data['students']
    
    if not isinstance(students_data, list):
        return APIResponse.validation_error({'students': 'Must be an array'})
    
    if len(students_data) == 0:
        return APIResponse.validation_error({'students': 'Array cannot be empty'})
    
    if len(students_data) > 100:
        return APIResponse.validation_error({'students': 'Maximum 100 students per request'})
    
    # Import results
    success_count = 0
    error_count = 0
    errors = []
    created_ids = []
    
    for idx, student_data in enumerate(students_data):
        student_id = student_data.get('student_id')
        fname = student_data.get('first_name')
        lname = student_data.get('last_name')
        email = student_data.get('email')
        
        # Validate required fields
        if not student_id or not fname or not lname:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': 'Missing required fields (student_id, first_name, last_name)'
            })
            continue
        
        # Check if student already exists
        existing = Student.query.get(student_id)
        if existing:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': 'Student already exists'
            })
            continue
        
        try:
            # Create student
            student = Student(
                student_id=student_id,
                fname=fname,
                lname=lname,
                email=email,
                phone=student_data.get('phone'),
                year_of_study=student_data.get('year_of_study', 1),
                current_semester=student_data.get('semester', '1.1'),
                is_active=True
            )
            
            db.session.add(student)
            
            # Create enrollment if course_code provided
            course_code = student_data.get('course_code')
            if course_code:
                enrollment = StudentCourse(
                    student_id=student_id,
                    course_code=course_code,
                    semester=student_data.get('semester', '1.1'),
                    year=student_data.get('year_of_study', 1),
                    status='Active'
                )
                db.session.add(enrollment)
            
            created_ids.append(student_id)
            success_count += 1
            
        except Exception as e:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': str(e)
            })
    
    # Commit successful imports
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='bulk_student_import',
        description=f'Imported {success_count} students via API'
    )
    
    response_data = {
        'success_count': success_count,
        'error_count': error_count,
        'total_records': len(students_data),
        'created_student_ids': created_ids,
        'errors': errors if error_count > 0 else []
    }
    
    if error_count > 0:
        return APIResponse.success(
            data=response_data,
            message=f"Import completed with {error_count} errors",
            status_code=207  # Multi-Status
        )
    
    return APIResponse.created(
        data=response_data,
        message="Students imported successfully"
    )