from flask_login import UserMixin
import sqlite3
from flask import current_app, g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

class Student(UserMixin):
    def __init__(self, student_id, fname, lname, email=None, phone=None, 
                 year_of_study=None, current_semester=None):
        self.id = student_id  # Required for Flask-Login
        self.student_id = student_id
        self.fname = fname
        self.lname = lname
        self.full_name = f"{fname} {lname}" if fname and lname else None
        self.email = email
        self.phone = phone
        self.year_of_study = year_of_study
        self.current_semester = current_semester
        self._courses = None  # Lazy loading for courses
    
    @staticmethod
    def get(student_id):
        db = get_db()
        student = db.execute('''
            SELECT s.student_id, s.fname, s.lname, s.email, s.phone,
                   s.year_of_study, s.current_semester,
                   GROUP_CONCAT(DISTINCT sc.course_code) as enrolled_courses,
                   GROUP_CONCAT(DISTINCT sc.semester) as enrolled_semesters
            FROM students s
            LEFT JOIN student_courses sc ON s.student_id = sc.student_id 
                AND sc.status = 'Active'
            WHERE s.student_id = ?
            GROUP BY s.student_id
        ''', (student_id,)).fetchone()
        
        if student is None:
            return None
        
        return Student(
            student_id=student['student_id'],
            fname=student['fname'],
            lname=student['lname'],
            email=student['email'],
            phone=student['phone'],
            year_of_study=student['year_of_study'],
            current_semester=student['current_semester']
        )
    
    @property
    def courses(self):
        """Get student's active courses"""
        if self._courses is None:
            db = get_db()
            courses = db.execute('''
                SELECT c.*, sc.semester, sc.enrollment_date, sc.status
                FROM student_courses sc
                JOIN courses c ON sc.course_code = c.course_code
                WHERE sc.student_id = ? AND sc.status = 'Active'
                ORDER BY sc.semester DESC, c.course_code
            ''', (self.student_id,)).fetchall()
            self._courses = [dict(course) for course in courses]
        return self._courses

    def get_classes(self):
        """Get student's current classes"""
        db = get_db()
        classes = db.execute('''
            SELECT DISTINCT cl.*
            FROM classes cl
            JOIN class_courses cc ON cl.class_id = cc.class_id
            JOIN student_courses sc ON cc.course_code = sc.course_code
            WHERE sc.student_id = ? AND sc.status = 'Active'
            ORDER BY cl.year, cl.semester
        ''', (self.student_id,)).fetchall()
        return [dict(cls) for cls in classes]

    def get_attendance_summary(self):
        """Get student's attendance summary"""
        db = get_db()
        summary = db.execute('''
            SELECT 
                COUNT(DISTINCT cs.session_id) as total_sessions,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN a.status = 'Absent' OR a.status IS NULL THEN 1 ELSE 0 END) as absent_count
            FROM class_sessions cs
            JOIN classes cl ON cs.class_id = cl.class_id
            JOIN class_courses cc ON cl.class_id = cc.class_id
            JOIN student_courses sc ON cc.course_code = sc.course_code
            LEFT JOIN attendance a ON cs.session_id = a.session_id 
                AND a.student_id = sc.student_id
            WHERE sc.student_id = ? AND sc.status = 'Active'
            AND cs.date <= date('now')
        ''', (self.student_id,)).fetchone()
        
        return {
            'total_sessions': summary['total_sessions'] or 0,
            'present_count': summary['present_count'] or 0,
            'absent_count': summary['absent_count'] or 0,
            'attendance_rate': (summary['present_count'] / summary['total_sessions'] * 100) 
                             if summary['total_sessions'] and summary['present_count'] else 0
        }

    def log_activity(self, activity_type):
        """Log student activity"""
        db = get_db()
        try:
            db.execute('''
                INSERT INTO activity_log (user_id, activity_type, timestamp)
                VALUES (?, ?, datetime('now'))
            ''', (self.student_id, activity_type))
            db.commit()
        except sqlite3.Error as e:
            print(f"Error logging activity: {e}")