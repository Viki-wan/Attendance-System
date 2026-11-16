"""
API Reports Endpoints
Report generation and export via API
"""
from flask import Blueprint, request, g
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import instructor_api_required, api_owns_resource
from app.middleware.rate_limiter import standard_rate_limit
from app.models.session import ClassSession
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.class_model import Class
from app.models.student_course import StudentCourse
from app.models.course import Course
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('api_reports', __name__, url_prefix='/api/v1/reports')


@bp.route('/session/<int:session_id>', methods=['GET'])
@api_owns_resource('session')
@standard_rate_limit
def get_session_report(session_id):
    """
    Generate comprehensive session report
    
    Query Parameters:
        - format: json (default) | summary
    
    Returns:
        Detailed session report with attendance breakdown
    """
    session = g.resource
    format_type = request.args.get('format', 'json')
    
    # Get class details
    class_obj = Class.query.get(session.class_id)
    course = Course.query.get(class_obj.course_code) if class_obj else None
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(session_id=session_id).all()
    
    # Status counts
    status_counts = {
        'Present': 0,
        'Absent': 0,
        'Late': 0,
        'Excused': 0
    }
    
    attendance_list = []
    for record in attendance_records:
        status_counts[record.status] += 1
        
        student = Student.query.get(record.student_id)
        attendance_list.append({
            'student_id': record.student_id,
            'student_name': f"{student.fname} {student.lname}" if student else None,
            'email': student.email if student else None,
            'status': record.status,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None,
            'method': record.method,
            'confidence_score': record.confidence_score
        })
    
    # Get enrolled students who didn't attend
    enrolled_students = db.session.query(Student).join(
        StudentCourse,
        Student.student_id == StudentCourse.student_id
    ).filter(
        StudentCourse.course_code == class_obj.course_code,
        StudentCourse.status == 'Active'
    ).all()
    
    attended_ids = [r.student_id for r in attendance_records]
    absent_students = []
    
    for student in enrolled_students:
        if student.student_id not in attended_ids:
            absent_students.append({
                'student_id': student.student_id,
                'student_name': f"{student.fname} {student.lname}",
                'email': student.email
            })
            status_counts['Absent'] += 1
    
    total_students = len(enrolled_students)
    attendance_percentage = round((status_counts['Present'] / total_students * 100), 2) if total_students > 0 else 0
    
    report_data = {
        'session_info': {
            'session_id': session.session_id,
            'class_id': session.class_id,
            'class_name': class_obj.class_name if class_obj else None,
            'course_code': class_obj.course_code if class_obj else None,
            'course_name': course.course_name if course else None,
            'date': session.date.isoformat() if isinstance(session.date, datetime) else session.date,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'status': session.status,
            'session_notes': session.session_notes
        },
        'attendance_summary': {
            'total_students': total_students,
            'present': status_counts['Present'],
            'absent': status_counts['Absent'],
            'late': status_counts['Late'],
            'excused': status_counts['Excused'],
            'attendance_percentage': attendance_percentage,
            'marked_count': len(attendance_records),
            'not_marked_count': total_students - len(attendance_records)
        },
        'attendance_details': attendance_list if format_type == 'json' else None,
        'absent_students': absent_students if format_type == 'json' else None,
        'generated_at': datetime.utcnow().isoformat(),
        'generated_by': g.user_id
    }
    
    # Remove None values if summary format
    if format_type == 'summary':
        report_data = {k: v for k, v in report_data.items() if v is not None}
    
    return APIResponse.success(
        data=report_data,
        message="Session report generated successfully"
    )


@bp.route('/class/<string:class_id>', methods=['GET'])
@api_owns_resource('class')
@standard_rate_limit
def get_class_report(class_id):
    """
    Generate class attendance report
    
    Query Parameters:
        - date_from: Start date (YYYY-MM-DD, default: 30 days ago)
        - date_to: End date (YYYY-MM-DD, default: today)
        - include_sessions: Include session details (true/false)
    
    Returns:
        Class attendance report with statistics
    """
    class_obj = g.resource
    
    # Date range
    date_to = request.args.get('date_to')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            return APIResponse.validation_error({'date_to': 'Invalid date format'})
    else:
        date_to_obj = datetime.now().date()
    
    date_from = request.args.get('date_from')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            return APIResponse.validation_error({'date_from': 'Invalid date format'})
    else:
        date_from_obj = date_to_obj - timedelta(days=30)
    
    include_sessions = request.args.get('include_sessions', 'false').lower() == 'true'
    
    # Get course details
    course = Course.query.get(class_obj.course_code)
    
    # Get sessions in date range
    sessions = ClassSession.query.filter(
        ClassSession.class_id == class_id,
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from_obj,
        ClassSession.date <= date_to_obj
    ).order_by(ClassSession.date.desc()).all()
    
    # Calculate statistics
    total_sessions = len(sessions)
    completed_sessions = len([s for s in sessions if s.status == 'completed'])
    
    # Average attendance
    if completed_sessions > 0:
        total_attendance = sum([
            (s.attendance_count / s.total_students * 100) if s.total_students > 0 else 0
            for s in sessions if s.status == 'completed'
        ])
        avg_attendance = round(total_attendance / completed_sessions, 2)
    else:
        avg_attendance = 0
    
    # Get enrolled students
    enrolled_students = db.session.query(Student).join(
        StudentCourse,
        Student.student_id == StudentCourse.student_id
    ).filter(
        StudentCourse.course_code == class_obj.course_code,
        StudentCourse.status == 'Active'
    ).all()
    
    # Student attendance breakdown
    student_stats = []
    session_ids = [s.session_id for s in sessions if s.status == 'completed']
    
    for student in enrolled_students:
        if session_ids:
            attended = Attendance.query.filter(
                Attendance.student_id == student.student_id,
                Attendance.session_id.in_(session_ids),
                Attendance.status.in_(['Present', 'Late'])
            ).count()
            
            percentage = round((attended / len(session_ids) * 100), 2) if session_ids else 0
        else:
            attended = 0
            percentage = 0
        
        student_stats.append({
            'student_id': student.student_id,
            'student_name': f"{student.fname} {student.lname}",
            'email': student.email,
            'sessions_attended': attended,
            'sessions_missed': len(session_ids) - attended,
            'attendance_percentage': percentage
        })
    
    # Sort by attendance percentage
    student_stats.sort(key=lambda x: x['attendance_percentage'])
    
    report_data = {
        'class_info': {
            'class_id': class_id,
            'class_name': class_obj.class_name,
            'course_code': class_obj.course_code,
            'course_name': course.course_name if course else None,
            'year': class_obj.year,
            'semester': class_obj.semester
        },
        'period': {
            'date_from': date_from_obj.isoformat(),
            'date_to': date_to_obj.isoformat(),
            'days': (date_to_obj - date_from_obj).days
        },
        'summary': {
            'total_students': len(enrolled_students),
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'scheduled_sessions': len([s for s in sessions if s.status == 'scheduled']),
            'average_attendance': avg_attendance
        },
        'student_attendance': student_stats,
        'generated_at': datetime.utcnow().isoformat(),
        'generated_by': g.user_id
    }
    
    # Include session details if requested
    if include_sessions:
        session_details = []
        for session in sessions:
            session_details.append({
                'session_id': session.session_id,
                'date': session.date.isoformat() if isinstance(session.date, datetime) else session.date,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'status': session.status,
                'attendance_count': session.attendance_count,
                'total_students': session.total_students,
                'attendance_percentage': round((session.attendance_count / session.total_students * 100), 2) if session.total_students > 0 else 0
            })
        report_data['sessions'] = session_details
    
    return APIResponse.success(
        data=report_data,
        message="Class report generated successfully"
    )


@bp.route('/student/<string:student_id>', methods=['GET'])
@instructor_api_required
@standard_rate_limit
def get_student_report(student_id):
    """
    Generate student attendance report
    
    Query Parameters:
        - date_from: Start date (YYYY-MM-DD, default: 30 days ago)
        - date_to: End date (YYYY-MM-DD, default: today)
        - class_id: Filter by specific class
    
    Returns:
        Student attendance report across all classes
    """
    student = Student.query.get(student_id)
    
    if not student:
        return APIResponse.not_found("Student")
    
    # Verify instructor has access
    from app.models.class_instructor import ClassInstructor
    instructor_classes = ClassInstructor.query.filter_by(
        instructor_id=g.user_id
    ).all()
    class_ids = [ic.class_id for ic in instructor_classes]
    classes = Class.query.filter(Class.class_id.in_(class_ids)).all()
    course_codes = [c.course_code for c in classes]
    
    # Check if student is in any of instructor's courses
    enrollment = StudentCourse.query.filter(
        StudentCourse.student_id == student_id,
        StudentCourse.course_code.in_(course_codes)
    ).first()
    
    if not enrollment:
        return APIResponse.forbidden("You don't have access to this student")
    
    # Date range
    date_to = request.args.get('date_to')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            return APIResponse.validation_error({'date_to': 'Invalid date format'})
    else:
        date_to_obj = datetime.now().date()
    
    date_from = request.args.get('date_from')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            return APIResponse.validation_error({'date_from': 'Invalid date format'})
    else:
        date_from_obj = date_to_obj - timedelta(days=30)
    
    class_id = request.args.get('class_id')
    
    # Build session query
    session_query = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from_obj,
        ClassSession.date <= date_to_obj,
        ClassSession.status == 'completed'
    )
    
    if class_id:
        session_query = session_query.filter_by(class_id=class_id)
    
    sessions = session_query.all()
    session_ids = [s.session_id for s in sessions]
    
    # Get attendance records
    if session_ids:
        attendance_records = Attendance.query.filter(
            Attendance.student_id == student_id,
            Attendance.session_id.in_(session_ids)
        ).all()
    else:
        attendance_records = []
    
    # Status counts
    status_counts = {
        'Present': 0,
        'Absent': 0,
        'Late': 0,
        'Excused': 0
    }
    
    attendance_details = []
    for record in attendance_records:
        status_counts[record.status] += 1
        
        session = ClassSession.query.get(record.session_id)
        class_obj = Class.query.get(session.class_id) if session else None
        
        attendance_details.append({
            'session_id': record.session_id,
            'class_id': session.class_id if session else None,
            'class_name': class_obj.class_name if class_obj else None,
            'date': session.date.isoformat() if session and isinstance(session.date, datetime) else session.date if session else None,
            'start_time': session.start_time if session else None,
            'status': record.status,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None,
            'method': record.method
        })
    
    # Calculate percentages
    total_sessions = len(sessions)
    sessions_attended = status_counts['Present'] + status_counts['Late']
    attendance_percentage = round((sessions_attended / total_sessions * 100), 2) if total_sessions > 0 else 0
    
    # Determine risk level
    if attendance_percentage < 50:
        risk_level = 'Critical'
    elif attendance_percentage < 65:
        risk_level = 'High'
    elif attendance_percentage < 75:
        risk_level = 'Medium'
    else:
        risk_level = 'Low'
    
    report_data = {
        'student_info': {
            'student_id': student_id,
            'name': f"{student.fname} {student.lname}",
            'email': student.email,
            'phone': student.phone,
            'year_of_study': student.year_of_study,
            'current_semester': student.current_semester
        },
        'period': {
            'date_from': date_from_obj.isoformat(),
            'date_to': date_to_obj.isoformat(),
            'days': (date_to_obj - date_from_obj).days
        },
        'summary': {
            'total_sessions': total_sessions,
            'sessions_attended': sessions_attended,
            'sessions_missed': total_sessions - sessions_attended,
            'present_count': status_counts['Present'],
            'absent_count': status_counts['Absent'],
            'late_count': status_counts['Late'],
            'excused_count': status_counts['Excused'],
            'attendance_percentage': attendance_percentage,
            'risk_level': risk_level
        },
        'attendance_details': attendance_details,
        'generated_at': datetime.utcnow().isoformat(),
        'generated_by': g.user_id
    }
    
    return APIResponse.success(
        data=report_data,
        message="Student report generated successfully"
    )


@bp.route('/generate', methods=['POST'])
@instructor_api_required
@standard_rate_limit
def generate_custom_report():
    """
    Generate custom report based on specified parameters
    
    Request Body:
        {
            "report_type": "attendance_summary|trend_analysis|comparison",
            "parameters": {
                "class_ids": ["string"],
                "student_ids": ["string"],
                "date_from": "YYYY-MM-DD",
                "date_to": "YYYY-MM-DD",
                "include_charts": boolean,
                "group_by": "class|student|date"
            }
        }
    
    Returns:
        Custom report based on parameters
    """
    data = request.get_json()
    
    if not data or 'report_type' not in data:
        return APIResponse.error("report_type is required", status_code=400)
    
    report_type = data['report_type']
    params = data.get('parameters', {})
    
    if report_type not in ['attendance_summary', 'trend_analysis', 'comparison']:
        return APIResponse.validation_error({
            'report_type': 'Invalid report type'
        })
    
    # Date range
    date_to_str = params.get('date_to')
    date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else datetime.now().date()
    
    date_from_str = params.get('date_from')
    date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else date_to_obj - timedelta(days=30)
    
    # Build query
    session_query = ClassSession.query.filter(
        ClassSession.created_by == g.user_id,
        ClassSession.date >= date_from_obj,
        ClassSession.date <= date_to_obj
    )
    
    # Filter by class IDs if provided
    class_ids = params.get('class_ids', [])
    if class_ids:
        session_query = session_query.filter(ClassSession.class_id.in_(class_ids))
    
    sessions = session_query.all()
    
    # Generate report based on type
    if report_type == 'attendance_summary':
        # Basic summary statistics
        total_sessions = len(sessions)
        completed = len([s for s in sessions if s.status == 'completed'])
        
        total_attendance = sum([
            s.attendance_count for s in sessions if s.status == 'completed'
        ])
        
        avg_attendance_rate = sum([
            (s.attendance_count / s.total_students * 100) if s.total_students > 0 else 0
            for s in sessions if s.status == 'completed'
        ]) / completed if completed > 0 else 0
        
        report_data = {
            'report_type': 'attendance_summary',
            'period': {
                'date_from': date_from_obj.isoformat(),
                'date_to': date_to_obj.isoformat()
            },
            'summary': {
                'total_sessions': total_sessions,
                'completed_sessions': completed,
                'total_attendance_marked': total_attendance,
                'average_attendance_rate': round(avg_attendance_rate, 2)
            }
        }
    
    elif report_type == 'trend_analysis':
        # Attendance trends over time
        daily_stats = {}
        for session in sessions:
            if session.status == 'completed':
                date_key = session.date.isoformat() if isinstance(session.date, datetime) else session.date
                if date_key not in daily_stats:
                    daily_stats[date_key] = {'count': 0, 'total_rate': 0}
                
                daily_stats[date_key]['count'] += 1
                rate = (session.attendance_count / session.total_students * 100) if session.total_students > 0 else 0
                daily_stats[date_key]['total_rate'] += rate
        
        trend_data = []
        for date_key in sorted(daily_stats.keys()):
            stats = daily_stats[date_key]
            avg_rate = stats['total_rate'] / stats['count'] if stats['count'] > 0 else 0
            trend_data.append({
                'date': date_key,
                'sessions': stats['count'],
                'average_attendance': round(avg_rate, 2)
            })
        
        report_data = {
            'report_type': 'trend_analysis',
            'period': {
                'date_from': date_from_obj.isoformat(),
                'date_to': date_to_obj.isoformat()
            },
            'trend_data': trend_data
        }
    
    else:  # comparison
        # Compare classes
        class_comparison = {}
        for session in sessions:
            if session.status == 'completed':
                if session.class_id not in class_comparison:
                    class_obj = Class.query.get(session.class_id)
                    class_comparison[session.class_id] = {
                        'class_name': class_obj.class_name if class_obj else session.class_id,
                        'sessions': 0,
                        'total_rate': 0
                    }
                
                class_comparison[session.class_id]['sessions'] += 1
                rate = (session.attendance_count / session.total_students * 100) if session.total_students > 0 else 0
                class_comparison[session.class_id]['total_rate'] += rate
        
        comparison_data = []
        for class_id, stats in class_comparison.items():
            avg_rate = stats['total_rate'] / stats['sessions'] if stats['sessions'] > 0 else 0
            comparison_data.append({
                'class_id': class_id,
                'class_name': stats['class_name'],
                'sessions': stats['sessions'],
                'average_attendance': round(avg_rate, 2)
            })
        
        comparison_data.sort(key=lambda x: x['average_attendance'], reverse=True)
        
        report_data = {
            'report_type': 'comparison',
            'period': {
                'date_from': date_from_obj.isoformat(),
                'date_to': date_to_obj.isoformat()
            },
            'comparison_data': comparison_data
        }
    
    report_data['generated_at'] = datetime.utcnow().isoformat()
    report_data['generated_by'] = g.user_id
    
    return APIResponse.success(
        data=report_data,
        message="Custom report generated successfully"
    )