"""
API Dashboard Endpoints
Dashboard statistics and data via API
"""
from flask import Blueprint, request, g
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import instructor_api_required
from app.middleware.rate_limiter import standard_rate_limit
from app.models.session import ClassSession
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.class_model import Class
from app.models.student_course import StudentCourse
from app.models.notification import Notification
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, and_

bp = Blueprint('api_dashboard', __name__, url_prefix='/api/v1/dashboard')


@bp.route('/stats', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_dashboard_stats():
    """
    Get comprehensive dashboard statistics
    
    Query Parameters:
        - period: today|week|month|custom (default: today)
        - date_from: Start date for custom period (YYYY-MM-DD)
        - date_to: End date for custom period (YYYY-MM-DD)
    
    Returns:
        Dashboard statistics including sessions, attendance, and alerts
    """
    period = request.args.get('period', 'today')
    
    # Determine date range
    today = datetime.now().date()
    
    if period == 'today':
        date_from = today
        date_to = today
    elif period == 'week':
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == 'month':
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == 'custom':
        date_from_str = request.args.get('date_from')
        date_to_str = request.args.get('date_to')
        
        if not date_from_str or not date_to_str:
            return APIResponse.validation_error({
                'date_from': 'Required for custom period' if not date_from_str else None,
                'date_to': 'Required for custom period' if not date_to_str else None
            })
        
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            return APIResponse.validation_error({'date': 'Invalid date format (use YYYY-MM-DD)'})
    else:
        return APIResponse.validation_error({'period': 'Invalid period value'})
    
    # Session statistics
    sessions_query = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.date <= date_to
    )
    
    total_sessions = sessions_query.count()
    completed_sessions = sessions_query.filter_by(status='completed').count()
    ongoing_sessions = sessions_query.filter_by(status='ongoing').count()
    scheduled_sessions = sessions_query.filter_by(status='scheduled').count()
    
    # Today's sessions
    today_sessions_query = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date == today
    )
    
    today_total = today_sessions_query.count()
    today_completed = today_sessions_query.filter_by(status='completed').count()
    today_pending = today_total - today_completed
    
    # Average attendance
    completed_sessions_list = sessions_query.filter_by(status='completed').all()
    
    if completed_sessions_list:
        total_attendance_rate = sum([
            (s.attendance_count / s.total_students * 100) if s.total_students > 0 else 0
            for s in completed_sessions_list
        ])
        avg_attendance = round(total_attendance_rate / len(completed_sessions_list), 2)
    else:
        avg_attendance = 0
    
    # Low attendance alerts (students below 75% in last 30 days)
    date_30_days_ago = today - timedelta(days=30)
    
    # Get all completed sessions in last 30 days
    recent_sessions = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_30_days_ago,
        ClassSession.status == 'completed'
    ).all()
    
    session_ids = [s.session_id for s in recent_sessions]
    
    low_attendance_count = 0
    if session_ids:
        # Get instructor's students
        from app.models.class_instructor import ClassInstructor
        instructor_classes = ClassInstructor.query.filter_by(
            instructor_id=g.user_id
        ).all()
        class_ids = [ic.class_id for ic in instructor_classes]
        classes = Class.query.filter(Class.class_id.in_(class_ids)).all()
        course_codes = [c.course_code for c in classes]
        
        students = db.session.query(Student).join(
            StudentCourse,
            Student.student_id == StudentCourse.student_id
        ).filter(
            StudentCourse.course_code.in_(course_codes),
            StudentCourse.status == 'Active'
        ).distinct().all()
        
        for student in students:
            attended = Attendance.query.filter(
                Attendance.student_id == student.student_id,
                Attendance.session_id.in_(session_ids),
                Attendance.status.in_(['Present', 'Late'])
            ).count()
            
            percentage = (attended / len(recent_sessions) * 100) if recent_sessions else 0
            
            if percentage < 75:
                low_attendance_count += 1
    
    # Unread notifications count
    unread_notifications = Notification.query.filter_by(
        user_id=g.user_id,
        user_type='instructor',
        is_read=False
    ).count()
    
    # Active classes count
    active_classes = len(set([s.class_id for s in sessions_query.all()]))
    
    stats_data = {
        'period': {
            'type': period,
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
            'days': (date_to - date_from).days + 1
        },
        'sessions': {
            'total': total_sessions,
            'completed': completed_sessions,
            'ongoing': ongoing_sessions,
            'scheduled': scheduled_sessions,
            'completion_rate': round((completed_sessions / total_sessions * 100), 2) if total_sessions > 0 else 0
        },
        'today': {
            'total_sessions': today_total,
            'completed_sessions': today_completed,
            'pending_sessions': today_pending
        },
        'attendance': {
            'average_percentage': avg_attendance,
            'low_attendance_alerts': low_attendance_count
        },
        'general': {
            'active_classes': active_classes,
            'unread_notifications': unread_notifications
        },
        'generated_at': datetime.utcnow().isoformat()
    }
    
    return APIResponse.success(
        data=stats_data,
        message="Dashboard statistics retrieved successfully"
    )


@bp.route('/today-sessions', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_today_sessions():
    """
    Get today's sessions with detailed status
    
    Query Parameters:
        - include_attendance: Include attendance summary (true/false)
    
    Returns:
        List of today's sessions with current status
    """
    today = datetime.now().date()
    current_time = datetime.now().time()
    
    include_attendance = request.args.get('include_attendance', 'false').lower() == 'true'
    
    # Get today's sessions
    sessions = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date == today
    ).order_by(ClassSession.start_time).all()
    
    sessions_data = []
    for session in sessions:
        class_obj = Class.query.get(session.class_id)
        
        # Determine real-time status
        try:
            start_time_obj = datetime.strptime(session.start_time, '%H:%M').time()
            end_time_obj = datetime.strptime(session.end_time, '%H:%M').time()
            
            if session.status == 'completed':
                real_status = 'completed'
            elif session.status == 'ongoing':
                real_status = 'in_progress'
            elif current_time < start_time_obj:
                real_status = 'upcoming'
            elif start_time_obj <= current_time <= end_time_obj:
                real_status = 'ready_to_start'
            else:
                real_status = 'missed'
        except:
            real_status = session.status
        
        session_data = {
            'session_id': session.session_id,
            'class_id': session.class_id,
            'class_name': class_obj.class_name if class_obj else None,
            'course_code': class_obj.course_code if class_obj else None,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'status': session.status,
            'real_time_status': real_status,
            'session_notes': session.session_notes
        }
        
        # Include attendance summary if requested
        if include_attendance:
            session_data['attendance'] = {
                'total_students': session.total_students,
                'attendance_count': session.attendance_count,
                'attendance_percentage': round((session.attendance_count / session.total_students * 100), 2) if session.total_students > 0 else 0,
                'not_marked': session.total_students - session.attendance_count
            }
        
        sessions_data.append(session_data)
    
    return APIResponse.success(
        data={
            'date': today.isoformat(),
            'total_sessions': len(sessions_data),
            'sessions': sessions_data
        },
        message="Today's sessions retrieved successfully"
    )


@bp.route('/alerts', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_alerts():
    """
    Get low attendance alerts
    
    Query Parameters:
        - threshold: Attendance percentage threshold (default: 75)
        - days: Number of days to analyze (default: 30)
        - limit: Maximum alerts to return (default: 20)
    
    Returns:
        List of students with low attendance
    """
    threshold = request.args.get('threshold', 75, type=int)
    days = request.args.get('days', 30, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    date_from = datetime.now().date() - timedelta(days=days)
    
    # Get completed sessions in period
    sessions = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from,
        ClassSession.status == 'completed'
    ).all()
    
    session_ids = [s.session_id for s in sessions]
    
    if not session_ids:
        return APIResponse.success(
            data={
                'threshold': threshold,
                'period_days': days,
                'alerts': []
            },
            message="No sessions in period"
        )
    
    # Get instructor's students
    from app.models.class_instructor import ClassInstructor
    instructor_classes = ClassInstructor.query.filter_by(
        instructor_id=g.user_id
    ).all()
    class_ids = [ic.class_id for ic in instructor_classes]
    classes = Class.query.filter(Class.class_id.in_(class_ids)).all()
    course_codes = [c.course_code for c in classes]
    
    students = db.session.query(Student).join(
        StudentCourse,
        Student.student_id == StudentCourse.student_id
    ).filter(
        StudentCourse.course_code.in_(course_codes),
        StudentCourse.status == 'Active'
    ).distinct().all()
    
    # Calculate attendance for each student
    alerts = []
    for student in students:
        attended = Attendance.query.filter(
            Attendance.student_id == student.student_id,
            Attendance.session_id.in_(session_ids),
            Attendance.status.in_(['Present', 'Late'])
        ).count()
        
        percentage = round((attended / len(sessions) * 100), 2) if sessions else 0
        
        if percentage < threshold:
            # Determine risk level
            if percentage < 50:
                risk_level = 'Critical'
            elif percentage < 65:
                risk_level = 'High'
            elif percentage < 75:
                risk_level = 'Medium'
            else:
                risk_level = 'Low'
            
            # Get student's classes
            student_enrollments = StudentCourse.query.filter_by(
                student_id=student.student_id,
                status='Active'
            ).all()
            
            enrolled_courses = [e.course_code for e in student_enrollments]
            
            alerts.append({
                'student_id': student.student_id,
                'student_name': f"{student.fname} {student.lname}",
                'email': student.email,
                'phone': student.phone,
                'total_sessions': len(sessions),
                'sessions_attended': attended,
                'sessions_missed': len(sessions) - attended,
                'attendance_percentage': percentage,
                'risk_level': risk_level,
                'enrolled_courses': enrolled_courses
            })
    
    # Sort by attendance percentage (lowest first)
    alerts.sort(key=lambda x: x['attendance_percentage'])
    
    # Limit results
    alerts = alerts[:limit]
    
    return APIResponse.success(
        data={
            'threshold': threshold,
            'period_days': days,
            'date_from': date_from.isoformat(),
            'date_to': datetime.now().date().isoformat(),
            'total_alerts': len(alerts),
            'alerts': alerts
        },
        message="Alerts retrieved successfully"
    )


@bp.route('/notifications', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_notifications():
    """
    Get instructor notifications
    
    Query Parameters:
        - unread_only: Show only unread (true/false, default: false)
        - limit: Maximum notifications to return (default: 20)
        - offset: Offset for pagination (default: 0)
    
    Returns:
        List of notifications
    """
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = min(request.args.get('limit', 20, type=int), 100)
    offset = request.args.get('offset', 0, type=int)
    
    # Build query
    query = Notification.query.filter_by(
        user_id=g.user_id,
        user_type='instructor'
    )
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    # Order by created_at descending
    query = query.order_by(Notification.created_at.desc())
    
    # Get total count
    total = query.count()
    
    # Apply limit and offset
    notifications = query.limit(limit).offset(offset).all()
    
    # Format response
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.type,
            'priority': notification.priority,
            'is_read': notification.is_read,
            'action_url': notification.action_url,
            'created_at': notification.created_at.isoformat() if notification.created_at else None,
            'expires_at': notification.expires_at.isoformat() if notification.expires_at else None
        })
    
    return APIResponse.success(
        data={
            'total_notifications': total,
            'unread_count': Notification.query.filter_by(
                user_id=g.user_id,
                user_type='instructor',
                is_read=False
            ).count(),
            'limit': limit,
            'offset': offset,
            'notifications': notifications_data
        },
        message="Notifications retrieved successfully"
    )


@bp.route('/notifications/<int:notification_id>/mark-read', methods=['POST'])
@instructor_api_required
@standard_rate_limit
def mark_notification_read(notification_id):
    """
    Mark a notification as read
    
    Returns:
        Success message
    """
    notification = Notification.query.get(notification_id)
    
    if not notification:
        return APIResponse.not_found("Notification")
    
    if notification.user_id != g.user_id or notification.user_type != 'instructor':
        return APIResponse.forbidden("You don't have access to this notification")
    
    notification.is_read = True
    db.session.commit()
    
    return APIResponse.success(
        data={'notification_id': notification_id, 'is_read': True},
        message="Notification marked as read"
    )


@bp.route('/upcoming-sessions', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_upcoming_sessions():
    """
    Get upcoming sessions (next 7 days)
    
    Query Parameters:
        - days: Number of days ahead (default: 7, max: 30)
    
    Returns:
        List of upcoming sessions grouped by date
    """
    days = min(request.args.get('days', 7, type=int), 30)
    
    today = datetime.now().date()
    end_date = today + timedelta(days=days)
    
    # Get upcoming sessions
    sessions = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= today,
        ClassSession.date <= end_date,
        ClassSession.status.in_(['scheduled', 'ongoing'])
    ).order_by(ClassSession.date, ClassSession.start_time).all()
    
    # Group by date
    sessions_by_date = {}
    for session in sessions:
        date_key = session.date.isoformat() if isinstance(session.date, datetime) else session.date
        
        if date_key not in sessions_by_date:
            sessions_by_date[date_key] = []
        
        class_obj = Class.query.get(session.class_id)
        
        sessions_by_date[date_key].append({
            'session_id': session.session_id,
            'class_id': session.class_id,
            'class_name': class_obj.class_name if class_obj else None,
            'course_code': class_obj.course_code if class_obj else None,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'status': session.status,
            'total_students': session.total_students
        })
    
    # Convert to list format
    upcoming_data = []
    for date_key in sorted(sessions_by_date.keys()):
        upcoming_data.append({
            'date': date_key,
            'session_count': len(sessions_by_date[date_key]),
            'sessions': sessions_by_date[date_key]
        })
    
    return APIResponse.success(
        data={
            'period': {
                'from': today.isoformat(),
                'to': end_date.isoformat(),
                'days': days
            },
            'total_sessions': len(sessions),
            'dates_with_sessions': len(upcoming_data),
            'upcoming_sessions': upcoming_data
        },
        message="Upcoming sessions retrieved successfully"
    )