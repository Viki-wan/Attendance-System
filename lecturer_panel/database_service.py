import sqlite3
import threading
import pickle
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from werkzeug.security import check_password_hash

class DatabaseService:
    """Database service layer for handling all database operations"""
    
    def __init__(self):
        self.db_path = None
        self.local = threading.local()
    
    def init_app(self, app):
        """Initialize the database service with Flask app"""
        self.db_path = app.config.get('DATABASE_PATH', 'attendance.db')
        self.create_indexes()
    
    @contextmanager
    def get_db(self):
        """Get database connection with automatic cleanup"""
        if not hasattr(self.local, 'db') or self.local.db is None:
            self.local.db = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.db.row_factory = sqlite3.Row
        
        try:
            yield self.local.db
        finally:
            # Don't close the connection, just commit any pending transactions
            self.local.db.commit()
    
    def execute_query(self, query: str, params: tuple = None) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results"""
        with self.get_db() as db:
            cursor = db.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self.get_db() as db:
            cursor = db.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            db.commit()
            return cursor.rowcount
    
    def create_indexes(self):
        """Create database indexes for performance optimization"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_attendance_student_session ON attendance(student_id, session_id)",
            "CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_class_sessions_date ON class_sessions(date)",
            "CREATE INDEX IF NOT EXISTS idx_class_sessions_class_id ON class_sessions(class_id)",
            "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
            "CREATE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_activity_log_user_id ON activity_log(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_class_instructors_class_id ON class_instructors(class_id)",
            "CREATE INDEX IF NOT EXISTS idx_class_instructors_instructor_id ON class_instructors(instructor_id)",
            "CREATE INDEX IF NOT EXISTS idx_student_courses_student_id ON student_courses(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_student_courses_course_code ON student_courses(course_code)",
            "CREATE INDEX IF NOT EXISTS idx_instructor_courses_instructor_id ON instructor_courses(instructor_id)"
        ]
        
        for index_query in indexes:
            try:
                self.execute_update(index_query)
            except sqlite3.Error as e:
                print(f"Error creating index: {e}")
    
    # Authentication methods
    def get_instructor_by_credentials(self, username: str, password: str) -> Optional[Dict]:
        """Get instructor by username and password"""
        # First check admin table for backwards compatibility
        admin_query = "SELECT * FROM admin WHERE username = ?"
        admin_result = self.execute_query(admin_query, (username,))
        
        if admin_result:
            admin = admin_result[0]
            if check_password_hash(admin['password'], password):
                return {
                    'id': admin['id'],
                    'username': admin['username'],
                    'is_admin': True,
                    'instructor_name': username,
                    'email': None,
                    'phone': None
                }
        
        # Check instructors table
        instructor_query = """
            SELECT * FROM instructors 
            WHERE instructor_name = ? OR email = ?
        """
        instructor_result = self.execute_query(instructor_query, (username, username))
        
        if instructor_result:
            instructor = instructor_result[0]
            if instructor.get('password') and check_password_hash(instructor['password'], password):
                return {
                    'id': instructor['instructor_id'],
                    'username': instructor['instructor_name'],
                    'is_admin': False,
                    'instructor_name': instructor['instructor_name'],
                    'email': instructor['email'],
                    'phone': instructor['phone']
                }
        
        return None
    
    def get_instructor_by_id(self, instructor_id: int) -> Optional[Dict]:
        """Get instructor by ID"""
        query = "SELECT * FROM instructors WHERE instructor_id = ?"
        result = self.execute_query(query, (instructor_id,))
        
        if result:
            instructor = result[0]
            return {
                'id': instructor['instructor_id'],
                'username': instructor['instructor_name'],
                'is_admin': False,
                'instructor_name': instructor['instructor_name'],
                'email': instructor['email'],
                'phone': instructor['phone']
            }
        return None
    
    def create_instructor(self, instructor_name: str, email: str, phone: str, password: str) -> int:
        """Create a new instructor"""
        query = """
            INSERT INTO instructors (instructor_name, email, phone, password)
            VALUES (?, ?, ?, ?)
        """
        with self.get_db() as db:
            cursor = db.cursor()
            cursor.execute(query, (instructor_name, email, phone, password))
            db.commit()
            return cursor.lastrowid
    
    def update_instructor_password(self, instructor_id: int, password: str) -> bool:
        """Update instructor password"""
        query = "UPDATE instructors SET password = ? WHERE instructor_id = ?"
        rows_affected = self.execute_update(query, (password, instructor_id))
        return rows_affected > 0
    
    # Student methods
    def get_students_by_course(self, course_code: str) -> List[Dict]:
        """Get all students enrolled in a specific course"""
        query = """
            SELECT s.*, sc.semester, sc.status as enrollment_status
            FROM students s
            JOIN student_courses sc ON s.student_id = sc.student_id
            WHERE sc.course_code = ? AND sc.status = 'Active'
            ORDER BY s.fname, s.lname
        """
        results = self.execute_query(query, (course_code,))
        return [dict(row) for row in results]
    
    def get_students_by_class(self, class_id: str) -> List[Dict]:
        """Get all students in a specific class"""
        query = """
            SELECT s.*, sc.semester, sc.status as enrollment_status
            FROM students s
            JOIN student_courses sc ON s.student_id = sc.student_id
            JOIN classes c ON sc.course_code = c.course_code
            WHERE c.class_id = ? AND sc.status = 'Active'
            ORDER BY s.fname, s.lname
        """
        results = self.execute_query(query, (class_id,))
        return [dict(row) for row in results]
    
    def get_student_by_id(self, student_id: str) -> Optional[Dict]:
        """Get student by ID"""
        query = "SELECT * FROM students WHERE student_id = ?"
        result = self.execute_query(query, (student_id,))
        
        if result:
            student = dict(result[0])
            # Deserialize face encoding if it exists
            if student.get('face_encoding'):
                try:
                    student['face_encoding'] = pickle.loads(student['face_encoding'])
                except:
                    student['face_encoding'] = None
            return student
        return None
    
    def get_all_students_with_encodings(self) -> List[Dict]:
        """Get all students with face encodings"""
        query = "SELECT * FROM students WHERE face_encoding IS NOT NULL"
        results = self.execute_query(query)
        
        students = []
        for row in results:
            student = dict(row)
            if student.get('face_encoding'):
                try:
                    student['face_encoding'] = pickle.loads(student['face_encoding'])
                    students.append(student)
                except:
                    continue
        
        return students
    
    # Session methods
    def get_class_sessions(self, class_id: str = None, date: str = None, instructor_id: int = None) -> List[Dict]:
        """Get class sessions with optional filtering"""
        query = """
            SELECT cs.*, c.class_name, c.course_code, co.course_name, c.year, c.semester
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.class_id
            JOIN courses co ON c.course_code = co.course_code
        """
        params = []
        
        # Add instructor filter if provided
        if instructor_id:
            query += " JOIN class_instructors ci ON c.class_id = ci.class_id"
        
        conditions = []
        if class_id:
            conditions.append("cs.class_id = ?")
            params.append(class_id)
        
        if date:
            conditions.append("cs.date = ?")
            params.append(date)
        
        if instructor_id:
            conditions.append("ci.instructor_id = ?")
            params.append(instructor_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY cs.date DESC, cs.start_time DESC"
        
        results = self.execute_query(query, tuple(params))
        return [dict(row) for row in results]
    
    def get_session_by_id(self, session_id: int) -> Optional[Dict]:
        """Get session by ID"""
        query = """
            SELECT cs.*, c.class_name, c.course_code, co.course_name, c.year, c.semester
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.class_id
            JOIN courses co ON c.course_code = co.course_code
            WHERE cs.session_id = ?
        """
        result = self.execute_query(query, (session_id,))
        
        if result:
            return dict(result[0])
        return None
    
    def create_session(self, class_id: str, date: str, start_time: str, end_time: str) -> int:
        """Create a new class session"""
        query = """
            INSERT INTO class_sessions (class_id, date, start_time, end_time, status)
            VALUES (?, ?, ?, ?, 'scheduled')
        """
        
        with self.get_db() as db:
            cursor = db.cursor()
            cursor.execute(query, (class_id, date, start_time, end_time))
            db.commit()
            return cursor.lastrowid
    
    def update_session_status(self, session_id: int, status: str) -> bool:
        """Update session status"""
        query = "UPDATE class_sessions SET status = ? WHERE session_id = ?"
        rows_affected = self.execute_update(query, (status, session_id))
        return rows_affected > 0
    
    # Attendance methods
    def get_attendance_for_session(self, session_id: int) -> List[Dict]:
        """Get attendance records for a specific session"""
        query = """
            SELECT a.*, s.fname, s.lname, s.student_id, s.image_path
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.session_id = ?
            ORDER BY s.fname, s.lname
        """
        results = self.execute_query(query, (session_id,))
        return [dict(row) for row in results]
    
    def mark_attendance(self, student_id: str, session_id: int, status: str = 'Present') -> bool:
        """Mark attendance for a student in a session"""
        query = """
            INSERT OR REPLACE INTO attendance (student_id, session_id, status, timestamp)
            VALUES (?, ?, ?, ?)
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows_affected = self.execute_update(query, (student_id, session_id, status, timestamp))
        return rows_affected > 0
    
    def get_attendance_stats(self, session_id: int) -> Dict:
        """Get attendance statistics for a session"""
        query = """
            SELECT 
                COUNT(*) as total_students,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_count
            FROM attendance
            WHERE session_id = ?
        """
        result = self.execute_query(query, (session_id,))
        
        if result:
            return dict(result[0])
        return {'total_students': 0, 'present_count': 0, 'absent_count': 0, 'late_count': 0}
    
    def get_attendance_summary(self, class_id: str = None, date_from: str = None, date_to: str = None) -> List[Dict]:
        """Get attendance summary with filters"""
        query = """
            SELECT 
                cs.session_id,
                cs.date,
                cs.start_time,
                cs.end_time,
                c.class_name,
                co.course_name,
                COUNT(a.id) as total_marked,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.class_id
            JOIN courses co ON c.course_code = co.course_code
            LEFT JOIN attendance a ON cs.session_id = a.session_id
        """
        
        params = []
        conditions = []
        
        if class_id:
            conditions.append("cs.class_id = ?")
            params.append(class_id)
        
        if date_from:
            conditions.append("cs.date >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("cs.date <= ?")
            params.append(date_to)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += """
            GROUP BY cs.session_id, cs.date, cs.start_time, cs.end_time, c.class_name, co.course_name
            ORDER BY cs.date DESC, cs.start_time DESC
        """
        
        results = self.execute_query(query, tuple(params))
        return [dict(row) for row in results]
    
    # Activity log methods
    def log_activity(self, user_id: str, activity_type: str):
        """Log user activity"""
        query = """
            INSERT INTO activity_log (user_id, activity_type, timestamp)
            VALUES (?, ?, ?)
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.execute_update(query, (user_id, activity_type, timestamp))
    
    def get_recent_activities(self, limit: int = 10) -> List[Dict]:
        """Get recent activities"""
        query = """
            SELECT * FROM activity_log
            ORDER BY timestamp DESC
            LIMIT ?
        """
        results = self.execute_query(query, (limit,))
        return [dict(row) for row in results]
    
    # Course methods
    def get_courses(self) -> List[Dict]:
        """Get all courses"""
        query = "SELECT * FROM courses ORDER BY course_name"
        results = self.execute_query(query)
        return [dict(row) for row in results]
    
    def get_course_by_code(self, course_code: str) -> Optional[Dict]:
        """Get course by code"""
        query = "SELECT * FROM courses WHERE course_code = ?"
        result = self.execute_query(query, (course_code,))
        
        if result:
            return dict(result[0])
        return None
    
    # Class methods
    def get_classes_for_instructor(self, instructor_id: int) -> List[Dict]:
        """Get classes assigned to an instructor"""
        query = """
            SELECT c.*, co.course_name, ci.instructor_id
            FROM classes c
            JOIN courses co ON c.course_code = co.course_code
            JOIN class_instructors ci ON c.class_id = ci.class_id
            WHERE ci.instructor_id = ?
            ORDER BY c.class_name
        """
        results = self.execute_query(query, (instructor_id,))
        return [dict(row) for row in results]
    
    def get_class_by_id(self, class_id: str) -> Optional[Dict]:
        """Get class by ID"""
        query = """
            SELECT c.*, co.course_name
            FROM classes c
            JOIN courses co ON c.course_code = co.course_code
            WHERE c.class_id = ?
        """
        result = self.execute_query(query, (class_id,))
        
        if result:
            return dict(result[0])
        return None
    
    def get_all_classes(self) -> List[Dict]:
        """Get all classes"""
        query = """
            SELECT c.*, co.course_name
            FROM classes c
            JOIN courses co ON c.course_code = co.course_code
            ORDER BY c.class_name
        """
        results = self.execute_query(query)
        return [dict(row) for row in results]
    
    # Settings methods
    def get_setting(self, key: str) -> Optional[str]:
        """Get setting value by key"""
        query = "SELECT setting_value FROM settings WHERE setting_key = ?"
        result = self.execute_query(query, (key,))
        
        if result:
            return result[0]['setting_value']
        return None
    
    def set_setting(self, key: str, value: str) -> bool:
        """Set setting value"""
        query = """
            INSERT OR REPLACE INTO settings (setting_key, setting_value)
            VALUES (?, ?)
        """
        rows_affected = self.execute_update(query, (key, value))
        return rows_affected > 0
    
    def get_all_settings(self) -> Dict[str, str]:
        """Get all settings as a dictionary"""
        query = "SELECT setting_key, setting_value FROM settings"
        results = self.execute_query(query)
        
        return {row['setting_key']: row['setting_value'] for row in results}
    
    def close(self):
        """Close database connection"""
        if hasattr(self.local, 'db') and self.local.db:
            self.local.db.close()
            self.local.db = None