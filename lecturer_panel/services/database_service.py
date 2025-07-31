"""
Database Service Layer for Face Recognition Attendance System
Handles all database operations for the lecturer panel
"""

import sqlite3
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from functools import wraps
import hashlib
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Database service layer providing all database operations
    for the lecturer panel face recognition attendance system
    """
    
    def __init__(self, db_path: str = "attendance.db"):
        """
        Initialize database service
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure database file exists and create if necessary"""
        if not os.path.exists(self.db_path):
            logger.warning(f"Database file {self.db_path} not found. Creating new database.")
            self._create_database()
    
    def _create_database(self):
        """Create database with schema (if needed)"""
        # This would typically run the schema from db.txt
        # For now, we assume the database already exists
        pass
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections
        Ensures proper connection handling and cleanup
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = (), fetch: str = 'none') -> Any:
        """
        Execute a database query with proper error handling
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: 'one', 'all', or 'none'
            
        Returns:
            Query result based on fetch type
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch == 'one':
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetch == 'all':
                results = cursor.fetchall()
                return [dict(row) for row in results]
            else:
                conn.commit()
                return cursor.rowcount
    
    @staticmethod
    def handle_db_error(func):
        """Decorator for database error handling"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except sqlite3.Error as e:
                logger.error(f"Database error in {func.__name__}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                raise
        return wrapper
    
    # ========== AUTHENTICATION SERVICES ==========
    
    @handle_db_error
    def authenticate_instructor(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate instructor login
        
        Args:
            username: Instructor name or email
            password: Plain text password (to be hashed)
            
        Returns:
            Instructor details if authenticated, None otherwise
        """
        # Hash password for comparison (implement proper hashing)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        query = """
        SELECT instructor_id, instructor_name, email, phone, faculty, 
               last_login, is_active, created_at
        FROM instructors 
        WHERE (instructor_name = ? OR email = ?) AND password = ? AND is_active = 1
        """
        
        instructor = self.execute_query(query, (username, username, password_hash), fetch='one')
        
        if instructor:
            # Update last login
            self.update_instructor_last_login(instructor['instructor_id'])
            
            # Log activity
            self.log_activity(
                user_id=str(instructor['instructor_id']),
                user_type='instructor',
                activity_type='login',
                description=f"Successful login for {instructor['instructor_name']}"
            )
        
        return instructor
    
    @handle_db_error
    def update_instructor_last_login(self, instructor_id: int):
        """Update instructor's last login timestamp"""
        query = "UPDATE instructors SET last_login = ? WHERE instructor_id = ?"
        self.execute_query(query, (datetime.now(), instructor_id))
    
    @handle_db_error
    def get_instructor_by_id(self, instructor_id: int) -> Optional[Dict]:
        """Get instructor details by ID"""
        query = """
        SELECT instructor_id, instructor_name, email, phone, faculty, 
               last_login, is_active, created_at, updated_at
        FROM instructors 
        WHERE instructor_id = ? AND is_active = 1
        """
        return self.execute_query(query, (instructor_id,), fetch='one')
    
    @handle_db_error
    def is_first_time_setup(self, instructor_id: int) -> bool:
        """Check if instructor needs first-time setup"""
        query = "SELECT last_login FROM instructors WHERE instructor_id = ?"
        result = self.execute_query(query, (instructor_id,), fetch='one')
        return result and result['last_login'] is None
    
    # ========== DASHBOARD SERVICES ==========
    
    @handle_db_error
    def get_dashboard_stats(self, instructor_id: int) -> Dict:
        """Get dashboard statistics for instructor"""
        stats = {}
        
        # Get today's sessions
        today = date.today().isoformat()
        
        # Today's sessions count
        query = """
        SELECT COUNT(*) as count FROM class_sessions cs
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        WHERE ci.instructor_id = ? AND cs.date = ?
        """
        result = self.execute_query(query, (instructor_id, today), fetch='one')
        stats['todays_sessions'] = result['count'] if result else 0
        
        # Active sessions count
        query = """
        SELECT COUNT(*) as count FROM class_sessions cs
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        WHERE ci.instructor_id = ? AND cs.status = 'ongoing'
        """
        result = self.execute_query(query, (instructor_id,), fetch='one')
        stats['active_sessions'] = result['count'] if result else 0
        
        # This week's attendance rate
        query = """
        SELECT 
            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_count,
            COUNT(*) as total_count
        FROM attendance a
        JOIN class_sessions cs ON a.session_id = cs.session_id
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        WHERE ci.instructor_id = ? 
        AND cs.date >= date('now', '-7 days')
        """
        result = self.execute_query(query, (instructor_id,), fetch='one')
        if result and result['total_count'] > 0:
            stats['attendance_rate'] = round((result['present_count'] / result['total_count']) * 100, 1)
        else:
            stats['attendance_rate'] = 0
        
        # Total students across all classes
        query = """
        SELECT COUNT(DISTINCT sc.student_id) as count
        FROM student_courses sc
        JOIN instructor_courses ic ON sc.course_code = ic.course_code
        WHERE ic.instructor_id = ? AND sc.status = 'Active'
        """
        result = self.execute_query(query, (instructor_id,), fetch='one')
        stats['total_students'] = result['count'] if result else 0
        
        return stats
    
    @handle_db_error
    def get_recent_sessions(self, instructor_id: int, limit: int = 5) -> List[Dict]:
        """Get recent sessions for instructor"""
        query = """
        SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time,
               cs.status, cs.attendance_count, cs.total_students,
               c.class_name, co.course_name
        FROM class_sessions cs
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        JOIN classes c ON cs.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        WHERE ci.instructor_id = ?
        ORDER BY cs.date DESC, cs.start_time DESC
        LIMIT ?
        """
        return self.execute_query(query, (instructor_id, limit), fetch='all')
    
    @handle_db_error
    def get_todays_schedule(self, instructor_id: int) -> List[Dict]:
        """Get today's schedule for instructor"""
        today = date.today().isoformat()
        day_of_week = date.today().weekday() + 1  # Convert to 1-7 format
        
        query = """
        SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time,
               cs.status, c.class_name, co.course_name,
               t.day_of_week
        FROM class_sessions cs
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        JOIN classes c ON cs.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        LEFT JOIN timetable t ON cs.class_id = t.class_id AND t.day_of_week = ?
        WHERE ci.instructor_id = ? AND cs.date = ?
        ORDER BY cs.start_time
        """
        return self.execute_query(query, (day_of_week, instructor_id, today), fetch='all')
    
    # ========== SESSION MANAGEMENT ==========
    
    @handle_db_error
    def get_instructor_sessions(self, instructor_id: int, date_filter: str = None, 
                               status_filter: str = None) -> List[Dict]:
        """Get sessions for instructor with optional filters"""
        query = """
        SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time,
               cs.status, cs.attendance_count, cs.total_students, cs.session_notes,
               c.class_name, co.course_name, co.course_code
        FROM class_sessions cs
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        JOIN classes c ON cs.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        WHERE ci.instructor_id = ?
        """
        params = [instructor_id]
        
        if date_filter:
            query += " AND cs.date = ?"
            params.append(date_filter)
        
        if status_filter:
            query += " AND cs.status = ?"
            params.append(status_filter)
        
        query += " ORDER BY cs.date DESC, cs.start_time DESC"
        
        return self.execute_query(query, tuple(params), fetch='all')
    
    @handle_db_error
    def get_session_details(self, session_id: int) -> Optional[Dict]:
        """Get detailed session information"""
        query = """
        SELECT cs.*, c.class_name, co.course_name, co.course_code,
               i.instructor_name
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        JOIN instructors i ON cs.created_by = i.instructor_id
        WHERE cs.session_id = ?
        """
        return self.execute_query(query, (session_id,), fetch='one')
    
    @handle_db_error
    def create_session(self, class_id: str, date: str, start_time: str, 
                      end_time: str, created_by: int) -> int:
        """Create a new class session"""
        query = """
        INSERT INTO class_sessions (class_id, date, start_time, end_time, 
                                   created_by, status)
        VALUES (?, ?, ?, ?, ?, 'scheduled')
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (class_id, date, start_time, end_time, created_by))
            session_id = cursor.lastrowid
            conn.commit()
            
            # Log activity
            self.log_activity(
                user_id=str(created_by),
                user_type='instructor',
                activity_type='session_created',
                description=f"Created session {session_id} for class {class_id}"
            )
            
            return session_id
    
    @handle_db_error
    def update_session_status(self, session_id: int, status: str, 
                             updated_by: int = None) -> bool:
        """Update session status"""
        query = "UPDATE class_sessions SET status = ? WHERE session_id = ?"
        rows_affected = self.execute_query(query, (status, session_id))
        
        if rows_affected > 0 and updated_by:
            self.log_activity(
                user_id=str(updated_by),
                user_type='instructor',
                activity_type='session_updated',
                description=f"Updated session {session_id} status to {status}"
            )
        
        return rows_affected > 0
    
    @handle_db_error
    def dismiss_session(self, session_id: int, instructor_id: int, 
                       reason: str, reschedule_date: str = None, 
                       reschedule_time: str = None, notes: str = None) -> bool:
        """Dismiss a session with reason"""
        # Update session status
        self.update_session_status(session_id, 'dismissed', instructor_id)
        
        # Record dismissal
        query = """
        INSERT INTO session_dismissals (session_id, instructor_id, reason, 
                                       rescheduled_to, rescheduled_time, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        rows_affected = self.execute_query(
            query, (session_id, instructor_id, reason, reschedule_date, 
                   reschedule_time, notes)
        )
        
        if rows_affected > 0:
            self.log_activity(
                user_id=str(instructor_id),
                user_type='instructor',
                activity_type='session_dismissed',
                description=f"Dismissed session {session_id}: {reason}"
            )
        
        return rows_affected > 0
    
    # ========== ATTENDANCE SERVICES ==========
    
    @handle_db_error
    def get_session_attendance(self, session_id: int) -> List[Dict]:
        """Get attendance for a specific session"""
        query = """
        SELECT a.*, s.student_id, s.fname, s.lname, s.email,
               s.course, s.year_of_study, s.current_semester
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.session_id = ?
        ORDER BY s.fname, s.lname
        """
        return self.execute_query(query, (session_id,), fetch='all')
    
    @handle_db_error
    def get_class_students(self, class_id: str) -> List[Dict]:
        """Get all students enrolled in a class"""
        query = """
        SELECT DISTINCT s.student_id, s.fname, s.lname, s.email,
               s.course, s.year_of_study, s.current_semester, s.image_path
        FROM students s
        JOIN student_courses sc ON s.student_id = sc.student_id
        JOIN classes c ON sc.course_code = c.course_code
        WHERE c.class_id = ? AND s.is_active = 1 AND sc.status = 'Active'
        ORDER BY s.fname, s.lname
        """
        return self.execute_query(query, (class_id,), fetch='all')
    
    @handle_db_error
    def mark_attendance(self, student_id: str, session_id: int, status: str,
                       marked_by: int, method: str = 'manual', 
                       confidence_score: float = None, notes: str = None) -> bool:
        """Mark attendance for a student"""
        query = """
        INSERT OR REPLACE INTO attendance 
        (student_id, session_id, status, marked_by, method, confidence_score, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        rows_affected = self.execute_query(
            query, (student_id, session_id, status, marked_by, method, 
                   confidence_score, notes)
        )
        
        if rows_affected > 0:
            # Update session attendance count
            self.update_session_attendance_count(session_id)
            
            # Log activity
            self.log_activity(
                user_id=str(marked_by),
                user_type='instructor',
                activity_type='attendance_marked',
                description=f"Marked {student_id} as {status} for session {session_id}"
            )
        
        return rows_affected > 0
    
    @handle_db_error
    def bulk_mark_attendance(self, attendance_data: List[Dict], 
                           marked_by: int) -> int:
        """Mark attendance for multiple students"""
        count = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for data in attendance_data:
                try:
                    cursor.execute("""
                    INSERT OR REPLACE INTO attendance 
                    (student_id, session_id, status, marked_by, method, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        data['student_id'], data['session_id'], data['status'],
                        marked_by, data.get('method', 'bulk'), data.get('notes', '')
                    ))
                    count += 1
                except sqlite3.Error as e:
                    logger.error(f"Error marking attendance for {data['student_id']}: {e}")
            
            conn.commit()
        
        # Update session attendance counts
        if count > 0:
            session_ids = list(set(data['session_id'] for data in attendance_data))
            for session_id in session_ids:
                self.update_session_attendance_count(session_id)
            
            # Log activity
            self.log_activity(
                user_id=str(marked_by),
                user_type='instructor',
                activity_type='bulk_attendance',
                description=f"Bulk marked attendance for {count} students"
            )
        
        return count
    
    @handle_db_error
    def update_session_attendance_count(self, session_id: int):
        """Update attendance count for a session"""
        query = """
        UPDATE class_sessions 
        SET attendance_count = (
            SELECT COUNT(*) FROM attendance 
            WHERE session_id = ? AND status = 'Present'
        ),
        total_students = (
            SELECT COUNT(DISTINCT s.student_id)
            FROM students s
            JOIN student_courses sc ON s.student_id = sc.student_id
            JOIN classes c ON sc.course_code = c.course_code
            JOIN class_sessions cs ON c.class_id = cs.class_id
            WHERE cs.session_id = ? AND s.is_active = 1 AND sc.status = 'Active'
        )
        WHERE session_id = ?
        """
        self.execute_query(query, (session_id, session_id, session_id))
    
    # ========== REPORTING SERVICES ==========
    
    @handle_db_error
    def get_attendance_report(self, instructor_id: int, date_from: str = None,
                            date_to: str = None, course_code: str = None,
                            class_id: str = None) -> List[Dict]:
        """Generate attendance report with filters"""
        query = """
        SELECT a.*, s.fname, s.lname, s.email, s.course, s.year_of_study,
               cs.date, cs.start_time, cs.end_time, cs.class_id,
               c.class_name, co.course_name
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        JOIN class_sessions cs ON a.session_id = cs.session_id
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        JOIN classes c ON cs.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        WHERE ci.instructor_id = ?
        """
        params = [instructor_id]
        
        if date_from:
            query += " AND cs.date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND cs.date <= ?"
            params.append(date_to)
        
        if course_code:
            query += " AND co.course_code = ?"
            params.append(course_code)
        
        if class_id:
            query += " AND cs.class_id = ?"
            params.append(class_id)
        
        query += " ORDER BY cs.date DESC, cs.start_time DESC, s.fname, s.lname"
        
        return self.execute_query(query, tuple(params), fetch='all')
    
    @handle_db_error
    def get_student_attendance_summary(self, student_id: str, 
                                     instructor_id: int = None) -> Dict:
        """Get attendance summary for a specific student"""
        query = """
        SELECT 
            COUNT(*) as total_sessions,
            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_count,
            COUNT(CASE WHEN a.status = 'Absent' THEN 1 END) as absent_count,
            COUNT(CASE WHEN a.status = 'Late' THEN 1 END) as late_count,
            COUNT(CASE WHEN a.status = 'Excused' THEN 1 END) as excused_count
        FROM attendance a
        JOIN class_sessions cs ON a.session_id = cs.session_id
        """
        params = [student_id]
        
        if instructor_id:
            query += """
            JOIN class_instructors ci ON cs.class_id = ci.class_id
            WHERE a.student_id = ? AND ci.instructor_id = ?
            """
            params.append(instructor_id)
        else:
            query += " WHERE a.student_id = ?"
        
        result = self.execute_query(query, tuple(params), fetch='one')
        
        if result and result['total_sessions'] > 0:
            result['attendance_rate'] = round(
                (result['present_count'] / result['total_sessions']) * 100, 2
            )
        else:
            result = {
                'total_sessions': 0, 'present_count': 0, 'absent_count': 0,
                'late_count': 0, 'excused_count': 0, 'attendance_rate': 0
            }
        
        return result
    
    # ========== COURSE & CLASS SERVICES ==========
    
    @handle_db_error
    def get_instructor_courses(self, instructor_id: int) -> List[Dict]:
        """Get courses assigned to instructor"""
        query = """
        SELECT co.*, ic.semester, ic.year, ic.is_coordinator
        FROM courses co
        JOIN instructor_courses ic ON co.course_code = ic.course_code
        WHERE ic.instructor_id = ? AND co.is_active = 1
        ORDER BY co.course_name
        """
        return self.execute_query(query, (instructor_id,), fetch='all')
    
    @handle_db_error
    def get_instructor_classes(self, instructor_id: int) -> List[Dict]:
        """Get classes assigned to instructor"""
        query = """
        SELECT c.*, co.course_name, co.faculty
        FROM classes c
        JOIN class_instructors ci ON c.class_id = ci.class_id
        JOIN courses co ON c.course_code = co.course_code
        WHERE ci.instructor_id = ? AND c.is_active = 1
        ORDER BY co.course_name, c.class_name
        """
        return self.execute_query(query, (instructor_id,), fetch='all')
    
    # ========== NOTIFICATION SERVICES ==========
    
    @handle_db_error
    def create_notification(self, user_id: str, user_type: str, title: str,
                          message: str, notification_type: str = 'info',
                          priority: str = 'normal', action_url: str = None,
                          expires_at: datetime = None) -> int:
        """Create a new notification"""
        query = """
        INSERT INTO notifications (user_id, user_type, title, message, type, 
                                 priority, action_url, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, user_type, title, message, 
                                 notification_type, priority, action_url, expires_at))
            notification_id = cursor.lastrowid
            conn.commit()
            return notification_id
    
    @handle_db_error
    def get_user_notifications(self, user_id: str, user_type: str, 
                             unread_only: bool = False, limit: int = 50) -> List[Dict]:
        """Get notifications for a user"""
        query = """
        SELECT * FROM notifications 
        WHERE user_id = ? AND user_type = ?
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        """
        params = [user_id, user_type]
        
        if unread_only:
            query += " AND is_read = 0"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        return self.execute_query(query, tuple(params), fetch='all')
    
    @handle_db_error
    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark a notification as read"""
        query = "UPDATE notifications SET is_read = 1 WHERE id = ?"
        return self.execute_query(query, (notification_id,)) > 0
    
    # ========== SETTINGS & PREFERENCES ==========
    
    @handle_db_error
    def get_lecturer_preferences(self, instructor_id: int) -> Dict:
        """Get lecturer preferences"""
        query = """
        SELECT * FROM lecturer_preferences 
        WHERE instructor_id = ?
        """
        result = self.execute_query(query, (instructor_id,), fetch='one')
        
        if not result:
            # Create default preferences
            self.create_default_lecturer_preferences(instructor_id)
            result = self.execute_query(query, (instructor_id,), fetch='one')
        
        # Parse JSON fields
        if result and result['notification_settings']:
            result['notification_settings'] = json.loads(result['notification_settings'])
        
        return result
    
    @handle_db_error
    def create_default_lecturer_preferences(self, instructor_id: int):
        """Create default preferences for lecturer"""
        query = """
        INSERT INTO lecturer_preferences (instructor_id, theme, dashboard_layout,
                                        notification_settings, auto_refresh_interval,
                                        default_session_duration, timezone, language)
        VALUES (?, 'light', 'default', '{}', 30, 90, 'UTC', 'en')
        """
        self.execute_query(query, (instructor_id,))
    
    @handle_db_error
    def update_lecturer_preferences(self, instructor_id: int, 
                                  preferences: Dict) -> bool:
        """Update lecturer preferences"""
        # Convert notification_settings to JSON if it's a dict
        if 'notification_settings' in preferences and isinstance(preferences['notification_settings'], dict):
            preferences['notification_settings'] = json.dumps(preferences['notification_settings'])
        
        # Build dynamic update query
        fields = []
        values = []
        
        for key, value in preferences.items():
            if key != 'instructor_id':  # Don't update the ID
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(instructor_id)
        query = f"UPDATE lecturer_preferences SET {', '.join(fields)} WHERE instructor_id = ?"
        
        return self.execute_query(query, tuple(values)) > 0
    
    @handle_db_error
    def get_system_setting(self, setting_key: str) -> Optional[str]:
        """Get system setting value"""
        query = "SELECT setting_value FROM settings WHERE setting_key = ?"
        result = self.execute_query(query, (setting_key,), fetch='one')
        return result['setting_value'] if result else None
    
    @handle_db_error
    def update_system_setting(self, setting_key: str, setting_value: str) -> bool:
        """Update system setting"""
        query = """
        INSERT OR REPLACE INTO settings (setting_key, setting_value, updated_at)
        VALUES (?, ?, datetime('now'))
        """
        return self.execute_query(query, (setting_key, setting_value)) > 0
    
    def load_settings(self) -> dict:
        """
        Load all system settings as a dictionary.
        """
        query = "SELECT setting_key, setting_value FROM settings"
        results = self.execute_query(query, fetch='all')
        return {row['setting_key']: row['setting_value'] for row in results}
    
    # ========== ACTIVITY LOGGING ==========
    
    @handle_db_error
    def log_activity(self, user_id: str, user_type: str, activity_type: str,
                    description: str = None):
        """Log user activity"""
        query = """
        INSERT INTO activity_log (user_id, user_type, activity_type, description)
        VALUES (?, ?, ?, ?)
        """
        self.execute_query(query, (user_id, user_type, activity_type, description))
    
    @handle_db_error
    def get_activity_log(self, user_id: str = None, user_type: str = None,
                        activity_type: str = None, limit: int = 100) -> List[Dict]:
        """Get activity log with optional filters"""
        query = "SELECT * FROM activity_log WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if user_type:
            query += " AND user_type = ?"
            params.append(user_type)
        
        if activity_type:
            query += " AND activity_type = ?"
            params.append(activity_type)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        return self.execute_query(query, tuple(params), fetch='all')
    
    @handle_db_error
    def cleanup_old_activity_logs(self, days_to_keep: int = 90):
        """Clean up old activity logs"""
        query = """
        DELETE FROM activity_log 
        WHERE timestamp < datetime('now', '-{} days')
        """.format(days_to_keep)
        
        rows_deleted = self.execute_query(query)
        
        if rows_deleted > 0:
            logger.info(f"Cleaned up {rows_deleted} old activity log entries")
        
        return rows_deleted
    
    # ========== SYSTEM METRICS ==========
    
    @handle_db_error
    def record_system_metric(self, metric_name: str, metric_value: float,
                           metric_unit: str = None, session_id: int = None,
                           instructor_id: int = None, additional_data: Dict = None) -> bool:
        """Record system metric"""
        query = """
        INSERT INTO system_metrics (metric_name, metric_value, metric_unit, 
                                  session_id, instructor_id, additional_data)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        additional_data_json = json.dumps(additional_data) if additional_data else None
        
        rows_affected = self.execute_query(
            query, (metric_name, metric_value, metric_unit, session_id, 
                   instructor_id, additional_data_json)
        )
        
        return rows_affected > 0
    
    @handle_db_error
    def get_system_metrics(self, metric_name: str = None, 
                          date_from: str = None, date_to: str = None,
                          instructor_id: int = None, limit: int = 100) -> List[Dict]:
        """Get system metrics with optional filters"""
        query = """
        SELECT sm.*, i.instructor_name, cs.class_id
        FROM system_metrics sm
        LEFT JOIN instructors i ON sm.instructor_id = i.instructor_id
        LEFT JOIN class_sessions cs ON sm.session_id = cs.session_id
        WHERE 1=1
        """
        params = []
        
        if metric_name:
            query += " AND sm.metric_name = ?"
            params.append(metric_name)
        
        if date_from:
            query += " AND sm.recorded_at >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND sm.recorded_at <= ?"
            params.append(date_to)
        
        if instructor_id:
            query += " AND sm.instructor_id = ?"
            params.append(instructor_id)
        
        query += " ORDER BY sm.recorded_at DESC LIMIT ?"
        params.append(limit)
        
        results = self.execute_query(query, tuple(params), fetch='all')
        
        # Parse additional_data JSON fields
        for result in results:
            if result.get('additional_data'):
                try:
                    result['additional_data'] = json.loads(result['additional_data'])
                except json.JSONDecodeError:
                    result['additional_data'] = {}
        
        return results
    
    @handle_db_error
    def get_metric_summary(self, metric_name: str, date_from: str = None,
                          date_to: str = None, instructor_id: int = None) -> Dict:
        """Get metric summary statistics"""
        query = """
        SELECT 
            COUNT(*) as count,
            AVG(metric_value) as avg_value,
            MIN(metric_value) as min_value,
            MAX(metric_value) as max_value,
            SUM(metric_value) as total_value
        FROM system_metrics
        WHERE metric_name = ?
        """
        params = [metric_name]
        
        if date_from:
            query += " AND recorded_at >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND recorded_at <= ?"
            params.append(date_to)
        
        if instructor_id:
            query += " AND instructor_id = ?"
            params.append(instructor_id)
        
        result = self.execute_query(query, tuple(params), fetch='one')
        
        if result:
            # Round numeric values
            for key in ['avg_value', 'min_value', 'max_value', 'total_value']:
                if result[key] is not None:
                    result[key] = round(result[key], 2)
        
        return result or {
            'count': 0, 'avg_value': 0, 'min_value': 0, 
            'max_value': 0, 'total_value': 0
        }
    
    # ========== TIMETABLE SERVICES ==========
    
    @handle_db_error
    def get_instructor_timetable(self, instructor_id: int, 
                               effective_date: str = None) -> List[Dict]:
        """Get instructor's timetable"""
        if not effective_date:
            effective_date = date.today().isoformat()
        
        query = """
        SELECT t.*, c.class_name, co.course_name, co.course_code
        FROM timetable t
        JOIN classes c ON t.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        JOIN class_instructors ci ON c.class_id = ci.class_id
        WHERE ci.instructor_id = ? AND t.is_active = 1
        AND t.effective_from <= ? 
        AND (t.effective_to IS NULL OR t.effective_to >= ?)
        ORDER BY t.day_of_week, t.start_time
        """
        
        return self.execute_query(query, (instructor_id, effective_date, effective_date), fetch='all')
    
    @handle_db_error
    def check_schedule_conflicts(self, class_id: str, day_of_week: int,
                               start_time: str, end_time: str,
                               exclude_id: int = None) -> List[Dict]:
        """Check for schedule conflicts"""
        query = """
        SELECT t.*, c.class_name, co.course_name
        FROM timetable t
        JOIN classes c ON t.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        WHERE t.day_of_week = ? AND t.is_active = 1
        AND (
            (t.start_time <= ? AND t.end_time > ?) OR
            (t.start_time < ? AND t.end_time >= ?) OR
            (t.start_time >= ? AND t.end_time <= ?)
        )
        """
        params = [day_of_week, start_time, start_time, end_time, end_time, start_time, end_time]
        
        if exclude_id:
            query += " AND t.id != ?"
            params.append(exclude_id)
        
        return self.execute_query(query, tuple(params), fetch='all')
    
    @handle_db_error
    def add_timetable_entry(self, class_id: str, day_of_week: int,
                          start_time: str, end_time: str,
                          effective_from: str = None, effective_to: str = None) -> int:
        """Add timetable entry"""
        if not effective_from:
            effective_from = date.today().isoformat()
        
        # Check for conflicts
        conflicts = self.check_schedule_conflicts(class_id, day_of_week, start_time, end_time)
        if conflicts:
            raise ValueError(f"Schedule conflict detected with existing classes")
        
        query = """
        INSERT INTO timetable (class_id, day_of_week, start_time, end_time,
                             effective_from, effective_to)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (class_id, day_of_week, start_time, end_time,
                                 effective_from, effective_to))
            timetable_id = cursor.lastrowid
            conn.commit()
            return timetable_id
    
    @handle_db_error
    def update_timetable_entry(self, timetable_id: int, **kwargs) -> bool:
        """Update timetable entry"""
        if not kwargs:
            return False
        
        # If updating schedule details, check for conflicts
        if any(key in kwargs for key in ['day_of_week', 'start_time', 'end_time']):
            # Get current entry
            current = self.execute_query(
                "SELECT * FROM timetable WHERE id = ?", (timetable_id,), fetch='one'
            )
            if current:
                conflicts = self.check_schedule_conflicts(
                    current['class_id'],
                    kwargs.get('day_of_week', current['day_of_week']),
                    kwargs.get('start_time', current['start_time']),
                    kwargs.get('end_time', current['end_time']),
                    exclude_id=timetable_id
                )
                if conflicts:
                    raise ValueError(f"Schedule conflict detected with existing classes")
        
        # Build update query
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['day_of_week', 'start_time', 'end_time', 'is_active', 
                      'effective_from', 'effective_to']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(timetable_id)
        query = f"UPDATE timetable SET {', '.join(fields)} WHERE id = ?"
        
        return self.execute_query(query, tuple(values)) > 0
    
    # ========== HOLIDAYS & BREAKS ==========
    
    @handle_db_error
    def get_holidays(self, date_from: str = None, date_to: str = None,
                    is_recurring: bool = None) -> List[Dict]:
        """Get holidays within date range"""
        query = "SELECT * FROM holidays WHERE 1=1"
        params = []
        
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        
        if is_recurring is not None:
            query += " AND is_recurring = ?"
            params.append(1 if is_recurring else 0)
        
        query += " ORDER BY date"
        
        return self.execute_query(query, tuple(params), fetch='all')
    
    @handle_db_error
    def add_holiday(self, name: str, date: str, description: str = None,
                   is_recurring: bool = False) -> int:
        """Add holiday"""
        query = """
        INSERT INTO holidays (name, date, description, is_recurring)
        VALUES (?, ?, ?, ?)
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (name, date, description, 1 if is_recurring else 0))
            holiday_id = cursor.lastrowid
            conn.commit()
            return holiday_id
    
    @handle_db_error
    def is_holiday(self, check_date: str) -> Optional[Dict]:
        """Check if a date is a holiday"""
        query = """
        SELECT * FROM holidays 
        WHERE date = ? OR (is_recurring = 1 AND substr(date, 6) = substr(?, 6))
        """
        return self.execute_query(query, (check_date, check_date), fetch='one')
    
    # ========== UTILITY METHODS ==========
    
    @handle_db_error
    def get_database_info(self) -> Dict:
        """Get database information and statistics"""
        info = {}
        
        # Get table counts
        tables = [
            'students', 'instructors', 'courses', 'classes', 'class_sessions',
            'attendance', 'notifications', 'activity_log', 'system_metrics'
        ]
        
        for table in tables:
            count = self.execute_query(f"SELECT COUNT(*) as count FROM {table}", fetch='one')
            info[f"{table}_count"] = count['count'] if count else 0
        
        # Get database size (SQLite specific)
        try:
            size_query = "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
            size_result = self.execute_query(size_query, fetch='one')
            info['database_size_bytes'] = size_result['size'] if size_result else 0
        except:
            info['database_size_bytes'] = 0
        
        # Get recent activity
        recent_activity = self.execute_query(
            "SELECT COUNT(*) as count FROM activity_log WHERE timestamp >= datetime('now', '-24 hours')",
            fetch='one'
        )
        info['recent_activity_count'] = recent_activity['count'] if recent_activity else 0
        
        return info
    
    @handle_db_error
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict:
        """Clean up old data based on retention policy"""
        cleanup_results = {}
        
        # Clean up old activity logs
        cleanup_results['activity_logs'] = self.cleanup_old_activity_logs(days_to_keep)
        
        # Clean up old notifications
        notification_query = """
        DELETE FROM notifications 
        WHERE created_at < datetime('now', '-{} days')
        AND is_read = 1
        """.format(days_to_keep)
        
        cleanup_results['notifications'] = self.execute_query(notification_query)
        
        # Clean up old system metrics
        metrics_query = """
        DELETE FROM system_metrics 
        WHERE recorded_at < datetime('now', '-{} days')
        """.format(days_to_keep)
        
        cleanup_results['system_metrics'] = self.execute_query(metrics_query)
        
        # Log cleanup activity
        total_cleaned = sum(cleanup_results.values())
        if total_cleaned > 0:
            self.log_activity(
                user_id='system',
                user_type='admin',
                activity_type='data_cleanup',
                description=f"Cleaned up {total_cleaned} old records"
            )
        
        return cleanup_results
    
    @handle_db_error
    def backup_database(self, backup_path: str = None) -> str:
        """Create database backup"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"attendance_system_backup_{timestamp}.db"
        
        import shutil
        shutil.copy2(self.db_path, backup_path)
        
        # Log backup activity
        self.log_activity(
            user_id='system',
            user_type='admin',
            activity_type='database_backup',
            description=f"Database backed up to {backup_path}"
        )
        
        return backup_path
    
    @handle_db_error
    def optimize_database(self) -> bool:
        """Optimize database performance"""
        try:
            with self.get_connection() as conn:
                # Analyze tables for query optimization
                conn.execute("ANALYZE")
                
                # Vacuum database to reclaim space
                conn.execute("VACUUM")
                
                # Update statistics
                conn.execute("REINDEX")
                
                conn.commit()
            
            # Log optimization activity
            self.log_activity(
                user_id='system',
                user_type='admin',
                activity_type='database_optimization',
                description="Database optimization completed"
            )
            
            return True
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return False
    
    # ========== TRANSACTION HELPERS ==========
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN TRANSACTION")
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type:
            logger.error(f"DatabaseService error: {exc_val}")
        return False

    @handle_db_error
    def get_todays_sessions_for_instructor(self, instructor_id: int) -> List[Dict]:
        """Get today's sessions for the instructor, filtered by status ('scheduled', 'ongoing')"""
        today = date.today().isoformat()
        query = """
        SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time,
               cs.status, c.class_name, co.course_name, co.course_code
        FROM class_sessions cs
        JOIN class_instructors ci ON cs.class_id = ci.class_id
        JOIN classes c ON cs.class_id = c.class_id
        JOIN courses co ON c.course_code = co.course_code
        WHERE ci.instructor_id = ? AND cs.date = ? AND cs.status IN ('scheduled', 'ongoing')
        ORDER BY cs.start_time
        """
        return self.execute_query(query, (instructor_id, today), fetch='all')


# Example usage and testing
if __name__ == "__main__":
    # Initialize database service
    db = DatabaseService()
    
    # Test database connection
    try:
        info = db.get_database_info()
        print("Database Info:", info)
        
        # Test authentication
        # instructor = db.authenticate_instructor("test_instructor", "password123")
        # print("Authentication test:", instructor)
        
        print("Database service initialized successfully!")
        
    except Exception as e:
        print(f"Database service error: {e}")
        logger.error(f"Database service initialization failed: {e}")
            