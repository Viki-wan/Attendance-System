"""
API Sessions Endpoints
CRUD operations for class sessions with ownership validation
"""
from flask import Blueprint, request, g
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import instructor_api_required, api_owns_resource
from app.middleware.rate_limiter import standard_rate_limit
from app.models.session import ClassSession
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.activity_log import ActivityLog
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('api_sessions', __name__, url_prefix='/api/v1/sessions')


@bp.route('/', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_sessions():
    """
    Get all sessions for current instructor
    
    Query Parameters:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)
        - status: Filter by status (scheduled, ongoing, completed, cancelled)
        - date_from: Filter from date (YYYY-MM-DD)
        - date_to: Filter to date (YYYY-MM-DD)
        - class_id: Filter by class ID
        - sort: Sort by field (date, created_at)
        - order: Sort order (asc, desc)
    
    Returns:
        Paginated list of sessions
    """
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Build query
    query = ClassSession.query.filter_by(created_by=g.user_id)
    
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
            return APIResponse.validation_error({'date_from': 'Invalid date format (use YYYY-MM-DD)'})
    
    date_to = request.args.get('date_to')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-</d').date()
            query = query.filter(ClassSession.date <= date_to_obj)
        except ValueError:
            return APIResponse.validation_error({'date_to': 'Invalid date format (use YYYY-MM-DD)'})
    
    class_id = request.args.get('class_id')
    if class_id:
        query = query.filter_by(class_id=class_id)
    
    # Sorting
    sort_field = request.args.get('sort', 'date')
    order = request.args.get('order', 'desc')
    
    if sort_field == 'date':
        sort_column = ClassSession.date
    elif sort_field == 'created_at':
        sort_column = ClassSession.created_at
    else:
        sort_column = ClassSession.date
    
    if order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    # Get total count
    total = query.count()
    
    # Paginate
    sessions = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    sessions_data = []
    for session in sessions.items:
        class_obj = Class.query.get(session.class_id)
        
        sessions_data.append({
            'session_id': session.session_id,
            'class_id': session.class_id,
            'class_name': class_obj.class_name if class_obj else None,
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
        message="Sessions retrieved successfully"
    )


@bp.route('/<int:session_id>', methods=['GET'])
@api_owns_resource('session')
@standard_rate_limit
def get_session(session_id):
    """
    Get single session details
    
    Returns:
        Full session details including attendance records
    """
    session = g.resource  # Set by api_owns_resource decorator
    class_obj = Class.query.get(session.class_id)
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(session_id=session_id).all()
    
    attendance_data = []
    for record in attendance_records:
        from app.models.student import Student
        student = Student.query.get(record.student_id)
        
        attendance_data.append({
            'student_id': record.student_id,
            'student_name': f"{student.fname} {student.lname}" if student else None,
            'status': record.status,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None,
            'method': record.method,
            'confidence_score': record.confidence_score,
            'notes': record.notes
        })
    
    session_data = {
        'session_id': session.session_id,
        'class_id': session.class_id,
        'class_name': class_obj.class_name if class_obj else None,
        'course_code': class_obj.course_code if class_obj else None,
        'date': session.date.isoformat() if isinstance(session.date, datetime) else session.date,
        'start_time': session.start_time,
        'end_time': session.end_time,
        'status': session.status,
        'attendance_count': session.attendance_count,
        'total_students': session.total_students,
        'attendance_percentage': round((session.attendance_count / session.total_students * 100), 2) if session.total_students > 0 else 0,
        'session_notes': session.session_notes,
        'created_at': session.created_at.isoformat() if session.created_at else None,
        'updated_at': session.updated_at.isoformat() if session.updated_at else None,
        'attendance_records': attendance_data
    }
    
    return APIResponse.success(
        data=session_data,
        message="Session retrieved successfully"
    )


@bp.route('/', methods=['POST'])
@instructor_api_required
@standard_rate_limit
def create_session():
    """
    Create new class session
    
    Request Body:
        {
            "class_id": "string",
            "date": "YYYY-MM-DD",
            "start_time": "HH:MM",
            "end_time": "HH:MM",
            "session_notes": "string (optional)"
        }
    
    Returns:
        Created session details
    """
    data = request.get_json()
    
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    # Validation
    required_fields = ['class_id', 'date', 'start_time', 'end_time']
    errors = {}
    
    for field in required_fields:
        if field not in data or not data[field]:
            errors[field] = f"{field.replace('_', ' ').title()} is required"
    
    if errors:
        return APIResponse.validation_error(errors)
    
    # Verify instructor owns the class
    from app.models.class_instructor import ClassInstructor
    assignment = ClassInstructor.query.filter_by(
        class_id=data['class_id'],
        instructor_id=g.user_id
    ).first()
    
    if not assignment:
        return APIResponse.forbidden("You are not assigned to this class")
    
    # Validate date format
    try:
        session_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return APIResponse.validation_error({'date': 'Invalid date format (use YYYY-MM-DD)'})
    
    # Get class and student count
    class_obj = Class.query.get(data['class_id'])
    if not class_obj:
        return APIResponse.not_found("Class")
    
    from app.models.student_course import StudentCourse
    student_count = StudentCourse.query.filter_by(
        course_code=class_obj.course_code,
        status='Active'
    ).count()
    
    # Create session
    session = ClassSession(
        class_id=data['class_id'],
        date=session_date,
        start_time=data['start_time'],
        end_time=data['end_time'],
        status='scheduled',
        created_by=g.user_id,
        session_notes=data.get('session_notes'),
        total_students=student_count,
        attendance_count=0
    )
    
    db.session.add(session)
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='session_created',
        description=f'Created session {session.session_id} for {class_obj.class_name} via API'
    )
    
    return APIResponse.created(
        data={
            'session_id': session.session_id,
            'class_id': session.class_id,
            'date': session.date.isoformat(),
            'start_time': session.start_time,
            'end_time': session.end_time,
            'status': session.status
        },
        message="Session created successfully",
        resource_id=session.session_id
    )


@bp.route('/<int:session_id>', methods=['PUT'])
@api_owns_resource('session')
@standard_rate_limit
def update_session(session_id):
    """
    Update session details
    
    Request Body:
        {
            "date": "YYYY-MM-DD (optional)",
            "start_time": "HH:MM (optional)",
            "end_time": "HH:MM (optional)",
            "session_notes": "string (optional)",
            "status": "string (optional)"
        }
    
    Returns:
        Updated session details
    """
    session = g.resource
    data = request.get_json()
    
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    # Update fields if provided
    if 'date' in data:
        try:
            session.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return APIResponse.validation_error({'date': 'Invalid date format (use YYYY-MM-DD)'})
    
    if 'start_time' in data:
        session.start_time = data['start_time']
    
    if 'end_time' in data:
        session.end_time = data['end_time']
    
    if 'session_notes' in data:
        session.session_notes = data['session_notes']
    
    if 'status' in data:
        if data['status'] not in ['scheduled', 'ongoing', 'completed', 'cancelled', 'dismissed']:
            return APIResponse.validation_error({'status': 'Invalid status value'})
        session.status = data['status']
    
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='session_updated',
        description=f'Updated session {session_id} via API'
    )
    
    return APIResponse.success(
        data={
            'session_id': session.session_id,
            'class_id': session.class_id,
            'date': session.date.isoformat() if isinstance(session.date, datetime) else session.date,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'status': session.status,
            'session_notes': session.session_notes
        },
        message="Session updated successfully"
    )


@bp.route('/<int:session_id>', methods=['DELETE'])
@api_owns_resource('session')
@standard_rate_limit
def delete_session(session_id):
    """
    Delete session (soft delete by setting status to cancelled)
    
    Returns:
        Success message
    """
    session = g.resource
    
    # Check if session has attendance records
    attendance_count = Attendance.query.filter_by(session_id=session_id).count()
    
    if attendance_count > 0:
        return APIResponse.error(
            "Cannot delete session with attendance records. Set status to cancelled instead.",
            error_code='SESSION_HAS_ATTENDANCE',
            status_code=409
        )
    
    # Soft delete by setting status
    session.status = 'cancelled'
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='session_deleted',
        description=f'Deleted session {session_id} via API'
    )
    
    return APIResponse.success(message="Session deleted successfully")


@bp.route('/statistics', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_statistics():
    """
    Get session statistics for instructor
    
    Query Parameters:
        - days: Number of days to include (default: 30)
        - class_id: Filter by specific class
    
    Returns:
        Session statistics
    """
    days = request.args.get('days', 30, type=int)
    class_id = request.args.get('class_id')
    
    date_from = datetime.now().date() - timedelta(days=days)
    
    # Build query
    query = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from
    )
    
    if class_id:
        query = query.filter_by(class_id=class_id)
    
    # Statistics
    total_sessions = query.count()
    completed_sessions = query.filter_by(status='completed').count()
    ongoing_sessions = query.filter_by(status='ongoing').count()
    scheduled_sessions = query.filter_by(status='scheduled').count()
    
    # Average attendance
    avg_attendance = db.session.query(
        func.avg(ClassSession.attendance_count * 100.0 / ClassSession.total_students)
    ).filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.total_students > 0,
        ClassSession.status == 'completed'
    ).scalar() or 0
    
    stats_data = {
        'period_days': days,
        'date_from': date_from.isoformat(),
        'date_to': datetime.now().date().isoformat(),
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'ongoing_sessions': ongoing_sessions,
        'scheduled_sessions': scheduled_sessions,
        'completion_rate': round((completed_sessions / total_sessions * 100), 2) if total_sessions > 0 else 0,
        'average_attendance': round(avg_attendance, 2)
    }
    
    return APIResponse.success(
        data=stats_data,
        message="Statistics retrieved successfully"
    )