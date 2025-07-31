from flask import Blueprint, render_template
from flask_login import login_required, current_user
from student_portal.models.db import get_db
from datetime import datetime, timedelta

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    db = get_db()
    
    # Get student information
    student = db.execute('''
        SELECT s.*, 
               GROUP_CONCAT(DISTINCT sc.course_code) as enrolled_courses
        FROM students s
        LEFT JOIN student_courses sc ON s.student_id = sc.student_id 
            AND sc.status = 'Active'
        WHERE s.student_id = ?
        GROUP BY s.student_id
    ''', (current_user.id,)).fetchone()
    
    # Get active courses for the current student
    courses = db.execute('''
        SELECT c.course_code, c.course_name, sc.semester 
        FROM student_courses sc 
        JOIN courses c ON sc.course_code = c.course_code 
        WHERE sc.student_id = ? AND sc.status = 'Active'
    ''', (current_user.id,)).fetchall()
    
    # Get upcoming sessions (next 7 days) for enrolled courses only
    today = datetime.now().strftime('%Y-%m-%d')
    next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    upcoming_sessions = db.execute('''
        SELECT DISTINCT
            cs.session_id, cs.date, cs.start_time, cs.end_time,
            cl.class_name, c.course_name, c.course_code
        FROM students s
        JOIN student_courses sc ON s.student_id = sc.student_id
        JOIN classes cl ON cl.course_code = sc.course_code 
            AND cl.semester = sc.semester
        JOIN class_sessions cs ON cs.class_id = cl.class_id
        JOIN courses c ON c.course_code = sc.course_code
        WHERE s.student_id = ?
            AND cs.date BETWEEN ? AND ?
            AND cs.status = 'scheduled'
            AND sc.status = 'Active'
        ORDER BY cs.date ASC, cs.start_time ASC
        LIMIT 5
    ''', (current_user.id, today, next_week)).fetchall()
    
    # Get attendance statistics
    attendance_stats = db.execute('''
        SELECT 
            COUNT(DISTINCT cs.session_id) as total_sessions,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count
        FROM class_sessions cs
        JOIN classes cl ON cs.class_id = cl.class_id
        JOIN class_courses cc ON cl.class_id = cc.class_id
        JOIN student_courses sc ON cc.course_code = sc.course_code
        LEFT JOIN attendance a ON cs.session_id = a.session_id 
            AND a.student_id = sc.student_id
        WHERE sc.student_id = ?
            AND sc.status = 'Active'
            AND cs.date <= date('now')
    ''', (current_user.id,)).fetchone()
    
    # Calculate attendance percentage
    attendance_percentage = 0
    if attendance_stats and attendance_stats['total_sessions'] > 0:
        attendance_percentage = round(
            (attendance_stats['present_count'] / attendance_stats['total_sessions']) * 100, 
            1
        )
    
    # Get recent attendance records
    recent_attendance = db.execute('''
        SELECT 
            a.timestamp, a.status, 
            cs.date, cs.start_time, cs.end_time,
            cl.class_name, c.course_name
        FROM attendance a
        JOIN class_sessions cs ON a.session_id = cs.session_id
        JOIN classes cl ON cs.class_id = cl.class_id
        JOIN class_courses cc ON cl.class_id = cc.class_id
        JOIN courses c ON cc.course_code = c.course_code
        WHERE a.student_id = ?
        ORDER BY cs.date DESC, cs.start_time DESC
        LIMIT 5
    ''', (current_user.id,)).fetchall()
    
    # Log dashboard view
    current_user.log_activity('view_dashboard')
    
    return render_template('dashboard/index.html', 
                         student=student,
                         courses=courses,
                         upcoming_sessions=upcoming_sessions,
                         attendance_percentage=attendance_percentage,
                         attendance_stats=attendance_stats,
                         recent_attendance=recent_attendance)