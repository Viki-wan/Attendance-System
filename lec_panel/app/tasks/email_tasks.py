from celery import shared_task
from app import create_app
from app.services.email_service import EmailService
from app.models.session import ClassSession
from app.models.user import Instructor
from datetime import datetime, timedelta

@shared_task
def send_session_reminders():
    """
    Celery task to send session reminders
    Run hourly to check for upcoming sessions
    """
    app = create_app()
    with app.app_context():
        # Get sessions starting in next hour
        now = datetime.now()
        one_hour_later = now + timedelta(hours=1)
        
        upcoming_sessions = ClassSession.query.filter(
            ClassSession.date == now.date(),
            ClassSession.start_time >= now.time(),
            ClassSession.start_time <= one_hour_later.time(),
            ClassSession.status == 'scheduled'
        ).all()
        
        for session in upcoming_sessions:
            if session.instructor and session.instructor.email:
                EmailService.send_session_reminder(
                    instructor=session.instructor,
                    session=session,
                    hours_before=1
                )

@shared_task
def send_weekly_summaries():
    """
    Celery task to send weekly summaries
    Run every Monday at 8 AM
    """
    app = create_app()
    with app.app_context():
        instructors = Instructor.query.filter_by(is_active=True).all()
        
        for instructor in instructors:
            # Calculate summary data
            summary_data = calculate_weekly_summary(instructor)
            
            if instructor.email:
                EmailService.send_weekly_summary(instructor, summary_data)

@shared_task
def check_low_attendance():
    """
    Celery task to check for low attendance
    Run daily at 6 PM
    """
    app = create_app()
    with app.app_context():
        from app.models.attendance import Attendance
        from app.models.course import Course
        
        # Get all active courses
        courses = Course.query.filter_by(is_active=True).all()
        
        for course in courses:
            # Get students with low attendance
            low_attendance_students = Attendance.get_low_attendance_students(
                course_code=course.course_code,
                threshold=75.0
            )
            
            # Get course instructors
            instructors = course.get_instructors()
            
            for student, attendance_rate in low_attendance_students:
                stats = Attendance.get_student_statistics(
                    student.student_id,
                    course_code=course.course_code
                )
                
                # Send alert to instructors
                for instructor in instructors:
                    if instructor.email:
                        EmailService.send_low_attendance_alert(
                            instructor=instructor,
                            student=student,
                            course_code=course.course_code,
                            attendance_stats=stats
                        )

def calculate_weekly_summary(instructor):
    """Calculate weekly summary data for instructor"""
    from datetime import date, timedelta
    
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Get sessions for the week
    sessions = ClassSession.get_by_instructor(
        instructor.instructor_id,
        start_date=week_start,
        end_date=week_end
    )
    
    total_sessions = len(sessions)
    if total_sessions == 0:
        return {
            'week_start': week_start.strftime('%B %d'),
            'week_end': week_end.strftime('%B %d'),
            'total_sessions': 0,
            'avg_attendance_rate': 0,
            'total_students': 0,
            'low_attendance_count': 0,
            'best_class': 'N/A',
            'attention_needed': 'No classes this week'
        }
    
    # Calculate statistics
    total_attendance_rate = sum(s.attendance_rate for s in sessions if s.attendance_rate)
    avg_attendance_rate = round(total_attendance_rate / total_sessions, 2)
    
    best_session = max(sessions, key=lambda s: s.attendance_rate)
    worst_session = min(sessions, key=lambda s: s.attendance_rate)
    
    return {
        'week_start': week_start.strftime('%B %d'),
        'week_end': week_end.strftime('%B %d'),
        'total_sessions': total_sessions,
        'avg_attendance_rate': avg_attendance_rate,
        'total_students': sum(s.total_students for s in sessions),
        'low_attendance_count': sum(1 for s in sessions if s.attendance_rate < 75),
        'best_class': best_session.class_.class_name if best_session else 'N/A',
        'attention_needed': worst_session.class_.class_name if worst_session.attendance_rate < 75 else None
    }
