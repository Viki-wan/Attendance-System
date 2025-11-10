"""
API Attendance Endpoints
Attendance management and marking operations via API
"""
from flask import Blueprint, request, g
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import instructor_api_required, api_owns_resource
from app.middleware.rate_limiter import standard_rate_limit
from app.models.session import ClassSession
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.activity_log import ActivityLog
from app import db
from datetime import datetime
from sqlalchemy import func

bp = Blueprint('api_attendance', __name__, url_prefix='/api/v1')


@bp.route('/sessions/<int:session_id>/attendance', methods=['GET'])
@api_owns_resource('session')
@standard_rate_limit
def get_session_attendance(session_id):
    """
    Get all attendance records for a session
    
    Query Parameters:
        - status: Filter by status (Present, Absent, Late, Excused)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 50, max: 200)
    
    Returns:
        Paginated list of attendance records with student details
    """
    session = g.resource
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    
    # Build query
    query = Attendance.query.filter_by(session_id=session_id)
    
    # Filter by status
    status = request.args.get('status')
    if status:
        if status not in ['Present', 'Absent', 'Late', 'Excused']:
            return APIResponse.validation_error({'status': 'Invalid status value'})
        query = query.filter_by(status=status)
    
    # Order by timestamp
    query = query.order_by(Attendance.timestamp.desc())
    
    # Get total count
    total = query.count()
    
    # Paginate
    attendance_records = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    attendance_data = []
    for record in attendance_records.items:
        student = Student.query.get(record.student_id)
        
        attendance_data.append({
            'id': record.id,
            'student_id': record.student_id,
            'student_name': f"{student.fname} {student.lname}" if student else None,
            'student_email': student.email if student else None,
            'status': record.status,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None,
            'method': record.method,
            'confidence_score': record.confidence_score,
            'marked_by': record.marked_by,
            'notes': record.notes
        })
    
    return APIResponse.paginated(
        data=attendance_data,
        page=page,
        per_page=per_page,
        total=total,
        message="Attendance records retrieved successfully"
    )


@bp.route('/sessions/<int:session_id>/attendance', methods=['POST'])
@api_owns_resource('session')
@standard_rate_limit
def mark_attendance(session_id):
    """
    Mark attendance for a student in a session
    
    Request Body:
        {
            "student_id": "string",
            "status": "Present|Absent|Late|Excused",
            "method": "manual|face_recognition|rfid (optional)",
            "confidence_score": float (optional, for face_recognition),
            "notes": "string (optional)"
        }
    
    Returns:
        Created attendance record
    """
    session = g.resource
    data = request.get_json()
    
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    # Validation
    student_id = data.get('student_id')
    status = data.get('status')
    
    if not student_id or not status:
        return APIResponse.validation_error({
            'student_id': 'Student ID is required' if not student_id else None,
            'status': 'Status is required' if not status else None
        })
    
    if status not in ['Present', 'Absent', 'Late', 'Excused']:
        return APIResponse.validation_error({'status': 'Invalid status value'})
    
    # Check if student exists
    student = Student.query.get(student_id)
    if not student:
        return APIResponse.not_found("Student")
    
    # Check if student is enrolled in the class
    from app.models.class_model import Class
    from app.models.student_course import StudentCourse
    
    class_obj = Class.query.get(session.class_id)
    enrollment = StudentCourse.query.filter_by(
        student_id=student_id,
        course_code=class_obj.course_code,
        status='Active'
    ).first()
    
    if not enrollment:
        return APIResponse.error(
            "Student is not enrolled in this class",
            error_code='STUDENT_NOT_ENROLLED',
            status_code=400
        )
    
    # Check if attendance already exists
    existing = Attendance.query.filter_by(
        student_id=student_id,
        session_id=session_id
    ).first()
    
    if existing:
        return APIResponse.error(
            "Attendance already marked for this student",
            error_code='ATTENDANCE_EXISTS',
            status_code=409
        )
    
    # Create attendance record
    attendance = Attendance(
        student_id=student_id,
        session_id=session_id,
        status=status,
        timestamp=datetime.utcnow(),
        marked_by=g.user_id,
        method=data.get('method', 'manual'),
        confidence_score=data.get('confidence_score'),
        notes=data.get('notes')
    )
    
    db.session.add(attendance)
    
    # Update session attendance count
    if status == 'Present':
        session.attendance_count += 1
    
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='attendance_marked',
        description=f'Marked {student_id} as {status} for session {session_id} via API'
    )
    
    return APIResponse.created(
        data={
            'id': attendance.id,
            'student_id': attendance.student_id,
            'session_id': attendance.session_id,
            'status': attendance.status,
            'timestamp': attendance.timestamp.isoformat(),
            'method': attendance.method
        },
        message="Attendance marked successfully",
        resource_id=attendance.id
    )


@bp.route('/sessions/<int:session_id>/attendance/bulk', methods=['POST'])
@api_owns_resource('session')
@standard_rate_limit
def bulk_mark_attendance(session_id):
    """
    Mark attendance for multiple students at once
    
    Request Body:
        {
            "attendance_records": [
                {
                    "student_id": "string",
                    "status": "Present|Absent|Late|Excused",
                    "method": "string (optional)",
                    "confidence_score": float (optional),
                    "notes": "string (optional)"
                },
                ...
            ]
        }
    
    Returns:
        Summary of bulk operation
    """
    session = g.resource
    data = request.get_json()
    
    if not data or 'attendance_records' not in data:
        return APIResponse.error("attendance_records array is required", status_code=400)
    
    records = data['attendance_records']
    
    if not isinstance(records, list):
        return APIResponse.validation_error({'attendance_records': 'Must be an array'})
    
    if len(records) == 0:
        return APIResponse.validation_error({'attendance_records': 'Array cannot be empty'})
    
    if len(records) > 100:
        return APIResponse.validation_error({'attendance_records': 'Maximum 100 records per request'})
    
    # Validation results
    success_count = 0
    error_count = 0
    errors = []
    created_ids = []
    
    for idx, record in enumerate(records):
        student_id = record.get('student_id')
        status = record.get('status')
        
        # Validate record
        if not student_id or not status:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': 'Missing required fields'
            })
            continue
        
        if status not in ['Present', 'Absent', 'Late', 'Excused']:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': 'Invalid status value'
            })
            continue
        
        # Check if student exists
        student = Student.query.get(student_id)
        if not student:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': 'Student not found'
            })
            continue
        
        # Check if attendance already exists
        existing = Attendance.query.filter_by(
            student_id=student_id,
            session_id=session_id
        ).first()
        
        if existing:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': 'Attendance already marked'
            })
            continue
        
        # Create attendance record
        try:
            attendance = Attendance(
                student_id=student_id,
                session_id=session_id,
                status=status,
                timestamp=datetime.utcnow(),
                marked_by=g.user_id,
                method=record.get('method', 'bulk_import'),
                confidence_score=record.get('confidence_score'),
                notes=record.get('notes')
            )
            
            db.session.add(attendance)
            
            # Update session attendance count
            if status == 'Present':
                session.attendance_count += 1
            
            created_ids.append(student_id)
            success_count += 1
            
        except Exception as e:
            error_count += 1
            errors.append({
                'index': idx,
                'student_id': student_id,
                'error': str(e)
            })
    
    # Commit all successful records
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='bulk_attendance_marked',
        description=f'Bulk marked attendance for {success_count} students in session {session_id} via API'
    )
    
    response_data = {
        'success_count': success_count,
        'error_count': error_count,
        'total_records': len(records),
        'created_student_ids': created_ids,
        'errors': errors if error_count > 0 else []
    }
    
    if error_count > 0:
        return APIResponse.success(
            data=response_data,
            message=f"Bulk operation completed with {error_count} errors",
            status_code=207  # Multi-Status
        )
    
    return APIResponse.success(
        data=response_data,
        message="Bulk attendance marked successfully"
    )


@bp.route('/attendance/<int:attendance_id>', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_attendance_record(attendance_id):
    """
    Get single attendance record details
    
    Returns:
        Attendance record with student details
    """
    attendance = Attendance.query.get(attendance_id)
    
    if not attendance:
        return APIResponse.not_found("Attendance record")
    
    # Verify ownership (instructor must own the session)
    session = ClassSession.query.get(attendance.session_id)
    if not session or session.created_by != g.user_id:
        return APIResponse.forbidden("You don't have access to this attendance record")
    
    # Get student details
    student = Student.query.get(attendance.student_id)
    
    attendance_data = {
        'id': attendance.id,
        'student_id': attendance.student_id,
        'student_name': f"{student.fname} {student.lname}" if student else None,
        'student_email': student.email if student else None,
        'session_id': attendance.session_id,
        'status': attendance.status,
        'timestamp': attendance.timestamp.isoformat() if attendance.timestamp else None,
        'method': attendance.method,
        'confidence_score': attendance.confidence_score,
        'marked_by': attendance.marked_by,
        'notes': attendance.notes
    }
    
    return APIResponse.success(
        data=attendance_data,
        message="Attendance record retrieved successfully"
    )


@bp.route('/attendance/<int:attendance_id>', methods=['PUT'])
@instructor_api_required
@standard_rate_limit
def update_attendance_record(attendance_id):
    """
    Update attendance record
    
    Request Body:
        {
            "status": "Present|Absent|Late|Excused (optional)",
            "notes": "string (optional)"
        }
    
    Returns:
        Updated attendance record
    """
    attendance = Attendance.query.get(attendance_id)
    
    if not attendance:
        return APIResponse.not_found("Attendance record")
    
    # Verify ownership
    session = ClassSession.query.get(attendance.session_id)
    if not session or session.created_by != g.user_id:
        return APIResponse.forbidden("You don't have access to this attendance record")
    
    data = request.get_json()
    
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    old_status = attendance.status
    
    # Update fields if provided
    if 'status' in data:
        new_status = data['status']
        if new_status not in ['Present', 'Absent', 'Late', 'Excused']:
            return APIResponse.validation_error({'status': 'Invalid status value'})
        
        attendance.status = new_status
        
        # Update session attendance count
        if old_status != 'Present' and new_status == 'Present':
            session.attendance_count += 1
        elif old_status == 'Present' and new_status != 'Present':
            session.attendance_count -= 1
    
    if 'notes' in data:
        attendance.notes = data['notes']
    
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='attendance_updated',
        description=f'Updated attendance {attendance_id} from {old_status} to {attendance.status} via API'
    )
    
    return APIResponse.success(
        data={
            'id': attendance.id,
            'student_id': attendance.student_id,
            'session_id': attendance.session_id,
            'status': attendance.status,
            'notes': attendance.notes
        },
        message="Attendance record updated successfully"
    )


@bp.route('/attendance/<int:attendance_id>', methods=['DELETE'])
@instructor_api_required
@standard_rate_limit
def delete_attendance_record(attendance_id):
    """
    Delete attendance record
    
    Returns:
        Success message
    """
    attendance = Attendance.query.get(attendance_id)
    
    if not attendance:
        return APIResponse.not_found("Attendance record")
    
    # Verify ownership
    session = ClassSession.query.get(attendance.session_id)
    if not session or session.created_by != g.user_id:
        return APIResponse.forbidden("You don't have access to this attendance record")
    
    # Update session attendance count
    if attendance.status == 'Present':
        session.attendance_count -= 1
    
    db.session.delete(attendance)
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='attendance_deleted',
        description=f'Deleted attendance record {attendance_id} via API'
    )
    
    return APIResponse.success(message="Attendance record deleted successfully")


@bp.route('/sessions/<int:session_id>/attendance/summary', methods=['GET'])
@api_owns_resource('session')
@standard_rate_limit
def get_attendance_summary(session_id):
    """
    Get attendance summary statistics for a session
    
    Returns:
        Summary statistics (present, absent, late, excused counts)
    """
    session = g.resource
    
    # Get counts by status
    status_counts = db.session.query(
        Attendance.status,
        func.count(Attendance.id)
    ).filter_by(session_id=session_id).group_by(Attendance.status).all()
    
    # Format counts
    counts = {
        'Present': 0,
        'Absent': 0,
        'Late': 0,
        'Excused': 0
    }
    
    for status, count in status_counts:
        counts[status] = count
    
    total_marked = sum(counts.values())
    
    summary_data = {
        'session_id': session_id,
        'total_students': session.total_students,
        'total_marked': total_marked,
        'not_marked': session.total_students - total_marked,
        'present_count': counts['Present'],
        'absent_count': counts['Absent'],
        'late_count': counts['Late'],
        'excused_count': counts['Excused'],
        'attendance_percentage': round((counts['Present'] / session.total_students * 100), 2) if session.total_students > 0 else 0,
        'completion_percentage': round((total_marked / session.total_students * 100), 2) if session.total_students > 0 else 0
    }
    
    return APIResponse.success(
        data=summary_data,
        message="Attendance summary retrieved successfully"
    )