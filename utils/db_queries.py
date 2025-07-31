"""
Database query helpers for generating attendance reports and analytics
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import os
import json

class AttendanceQueries:
    def __init__(self, db_path=None):
        """Initialize with path to database"""
        self.db_path = db_path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'attendance.db')
    
    def get_connection(self):
        """Get a database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable row factory for named columns
            return conn
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None
            
    def fetch_all_courses(self):
        """Fetch all courses for filtering"""
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_code")
            courses = [{"code": row["course_code"], "name": row["course_name"]} for row in cursor.fetchall()]
            return courses
        except sqlite3.Error as e:
            print(f"Error fetching courses: {e}")
            return []
        finally:
            conn.close()
            
    def fetch_all_classes(self, course_code=None):
        """Fetch all classes, optionally filtered by course"""
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            if course_code:
                cursor.execute("""
                    SELECT class_id, class_name, course_code
                    FROM classes
                    WHERE course_code = ?
                    ORDER BY class_id
                """, (course_code,))
            else:
                cursor.execute("""
                    SELECT class_id, class_name, course_code
                    FROM classes
                    ORDER BY course_code, class_id
                """)
            
            classes = [{"id": row["class_id"], "name": row["class_name"], "course": row["course_code"]} 
                       for row in cursor.fetchall()]
            return classes
        except sqlite3.Error as e:
            print(f"Error fetching classes: {e}")
            return []
        finally:
            conn.close()
            
    def fetch_all_instructors(self):
        """Fetch all instructors for filtering"""
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT instructor_id, instructor_name
                FROM instructors
                ORDER BY instructor_name
            """)
            
            instructors = [{"id": row["instructor_id"], "name": row["instructor_name"]} 
                           for row in cursor.fetchall()]
            return instructors
        except sqlite3.Error as e:
            print(f"Error fetching instructors: {e}")
            return []
        finally:
            conn.close()
    
    def fetch_date_range(self):
        """Fetch the earliest and latest session dates"""
        conn = self.get_connection()
        if not conn:
            return (datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d"))
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(date) as min_date, MAX(date) as max_date FROM class_sessions")
            row = cursor.fetchone()
            
            min_date = row["min_date"] if row["min_date"] else datetime.now().strftime("%Y-%m-%d")
            max_date = row["max_date"] if row["max_date"] else datetime.now().strftime("%Y-%m-%d")
            
            return (min_date, max_date)
        except sqlite3.Error as e:
            print(f"Error fetching date range: {e}")
            return (datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d"))
        finally:
            conn.close()
    
    def get_daily_attendance(self, date=None):
        """Get attendance data for a specific day"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            query = """
                SELECT 
                    cs.session_id,
                    cs.class_id,
                    cs.date,
                    cs.start_time,
                    cs.end_time,
                    c.course_code,
                    c.class_name,
                    i.instructor_name,
                    (SELECT COUNT(*) FROM attendance a WHERE a.session_id = cs.session_id) as present_count,
                    (SELECT COUNT(*) 
                        FROM students s
                        JOIN student_courses sc ON s.student_id = sc.student_id
                        WHERE sc.course_code = c.course_code
                    ) as total_students
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN class_instructors ci ON c.class_id = ci.class_id
                LEFT JOIN instructors i ON ci.instructor_id = i.instructor_id
                WHERE cs.date = ?
                ORDER BY cs.start_time
            """
            
            return pd.read_sql_query(query, conn, params=(date,))
        except sqlite3.Error as e:
            print(f"Error fetching daily attendance: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_course_attendance(self, course_code, start_date=None, end_date=None):
        """Get attendance data for a specific course over a date range"""
        now = datetime.now()
        end_date = end_date or now.strftime("%Y-%m-%d")
        start_date = start_date or (now - timedelta(days=30)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            query = """
                SELECT 
                    cs.session_id,
                    cs.class_id,
                    cs.date,
                    cs.start_time,
                    c.course_code,
                    c.class_name,
                    (SELECT COUNT(*) FROM attendance a WHERE a.session_id = cs.session_id) as present_count,
                    (SELECT COUNT(*) 
                        FROM students s
                        JOIN student_courses sc ON s.student_id = sc.student_id
                        WHERE sc.course_code = c.course_code
                    ) as total_students
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                WHERE c.course_code = ? AND cs.date BETWEEN ? AND ?
                ORDER BY cs.date, cs.start_time
            """
            
            return pd.read_sql_query(query, conn, params=(course_code, start_date, end_date))
        except sqlite3.Error as e:
            print(f"Error fetching course attendance: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_student_attendance(self, student_id=None, course_code=None, start_date=None, end_date=None):
        """Get attendance data for a specific student, optionally filtered by course"""
        now = datetime.now()
        end_date = end_date or now.strftime("%Y-%m-%d")
        start_date = start_date or (now - timedelta(days=30)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            params = []
            query = """
                SELECT 
                    s.student_id,
                    s.fname || ' ' || s.lname as student_name,
                    cs.session_id,
                    cs.class_id,
                    cs.date,
                    cs.start_time,
                    c.course_code,
                    c.class_name,
                    CASE WHEN a.id IS NULL THEN 'Absent' ELSE 'Present' END as status
                FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                JOIN classes c ON sc.course_code = c.course_code
                JOIN class_sessions cs ON c.class_id = cs.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id AND s.student_id = a.student_id
                WHERE cs.date BETWEEN ? AND ?
            """
            params.extend([start_date, end_date])
            
            if student_id:
                query += " AND s.student_id = ?"
                params.append(student_id)
                
            if course_code:
                query += " AND c.course_code = ?"
                params.append(course_code)
                
            query += " ORDER BY cs.date, cs.start_time, student_name"
            
            return pd.read_sql_query(query, conn, params=params)
        except sqlite3.Error as e:
            print(f"Error fetching student attendance: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_class_attendance_stats(self, class_id=None, start_date=None, end_date=None):
        """Get attendance statistics for a class"""
        now = datetime.now()
        end_date = end_date or now.strftime("%Y-%m-%d")
        start_date = start_date or (now - timedelta(days=30)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            params = [start_date, end_date]
            where_clause = "WHERE cs.date BETWEEN ? AND ?"
            
            if class_id:
                where_clause += " AND cs.class_id = ?"
                params.append(class_id)
                
            query = f"""
                SELECT 
                    cs.class_id,
                    c.class_name,
                    c.course_code,
                    cs.date,
                    COUNT(DISTINCT cs.session_id) as sessions_count,
                    COUNT(DISTINCT a.student_id) as students_present,
                    (SELECT COUNT(DISTINCT s.student_id) 
                     FROM students s
                     JOIN student_courses sc ON s.student_id = sc.student_id
                     WHERE sc.course_code = c.course_code) as total_enrolled
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id
                {where_clause}
                GROUP BY cs.class_id, cs.date
                ORDER BY cs.date
            """
            
            return pd.read_sql_query(query, conn, params=params)
        except sqlite3.Error as e:
            print(f"Error fetching class attendance stats: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_instructor_attendance_stats(self, instructor_id=None, start_date=None, end_date=None):
        """Get attendance statistics grouped by instructor"""
        now = datetime.now()
        end_date = end_date or now.strftime("%Y-%m-%d")
        start_date = start_date or (now - timedelta(days=30)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            params = [start_date, end_date]
            where_clause = "WHERE cs.date BETWEEN ? AND ?"
            
            if instructor_id:
                where_clause += " AND ci.instructor_id = ?"
                params.append(instructor_id)
                
            query = f"""
                SELECT 
                    i.instructor_id,
                    i.instructor_name,
                    c.course_code,
                    c.class_name,
                    COUNT(DISTINCT cs.session_id) as sessions_count,
                    COUNT(DISTINCT a.student_id) as total_attendance,
                    (SELECT COUNT(DISTINCT s.student_id) 
                     FROM students s
                     JOIN student_courses sc ON s.student_id = sc.student_id
                     WHERE sc.course_code = c.course_code) as total_students,
                    (COUNT(DISTINCT a.student_id) * 1.0 / 
                        (SELECT COUNT(DISTINCT s.student_id) 
                         FROM students s
                         JOIN student_courses sc ON s.student_id = sc.student_id
                         WHERE sc.course_code = c.course_code) * COUNT(DISTINCT cs.session_id)) as attendance_rate
                FROM instructors i
                JOIN class_instructors ci ON i.instructor_id = ci.instructor_id
                JOIN classes c ON ci.class_id = c.class_id
                JOIN class_sessions cs ON c.class_id = cs.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id
                {where_clause}
                GROUP BY i.instructor_id, c.course_code
                ORDER BY i.instructor_name, c.course_code
            """
            
            return pd.read_sql_query(query, conn, params=params)
        except sqlite3.Error as e:
            print(f"Error fetching instructor attendance stats: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_attendance_trends(self, course_code=None, class_id=None, weeks=12):
        """Get attendance trends over a period of weeks"""
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks)
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            params = [start_date.strftime("%Y-%m-%d")]
            where_clause = "WHERE cs.date >= ?"
            
            if course_code:
                where_clause += " AND c.course_code = ?"
                params.append(course_code)
                
            if class_id:
                where_clause += " AND cs.class_id = ?"
                params.append(class_id)
                
            query = f"""
                SELECT 
                    c.course_code,
                    c.class_name,
                    cs.date,
                    strftime('%W', cs.date) as week_number,
                    strftime('%Y', cs.date) as year,
                    COUNT(DISTINCT a.student_id) as students_present,
                    (SELECT COUNT(DISTINCT s.student_id) 
                     FROM students s
                     JOIN student_courses sc ON s.student_id = sc.student_id
                     WHERE sc.course_code = c.course_code) as total_enrolled,
                    (COUNT(DISTINCT a.student_id) * 100.0 / 
                        (SELECT COUNT(DISTINCT s.student_id) 
                         FROM students s
                         JOIN student_courses sc ON s.student_id = sc.student_id
                         WHERE sc.course_code = c.course_code)) as attendance_percentage
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id
                {where_clause}
                GROUP BY c.course_code, cs.date
                ORDER BY cs.date
            """
            
            return pd.read_sql_query(query, conn, params=params)
        except sqlite3.Error as e:
            print(f"Error fetching attendance trends: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_attendance_by_time_of_day(self, course_code=None, start_date=None, end_date=None):
        """Get attendance patterns by time of day"""
        now = datetime.now()
        end_date = end_date or now.strftime("%Y-%m-%d")
        start_date = start_date or (now - timedelta(days=90)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            params = [start_date, end_date]
            where_clause = "WHERE cs.date BETWEEN ? AND ?"
            
            if course_code:
                where_clause += " AND c.course_code = ?"
                params.append(course_code)
                
            query = f"""
                SELECT 
                    c.course_code,
                    CASE 
                        WHEN time(cs.start_time) < time('09:00:00') THEN 'Early Morning (before 9 AM)'
                        WHEN time(cs.start_time) < time('12:00:00') THEN 'Morning (9 AM - 12 PM)'
                        WHEN time(cs.start_time) < time('15:00:00') THEN 'Afternoon (12 PM - 3 PM)'
                        WHEN time(cs.start_time) < time('18:00:00') THEN 'Late Afternoon (3 PM - 6 PM)'
                        ELSE 'Evening (after 6 PM)'
                    END as time_block,
                    COUNT(DISTINCT cs.session_id) as sessions_count,
                    COUNT(DISTINCT a.student_id) as students_present,
                    (SELECT COUNT(DISTINCT s.student_id) 
                     FROM students s
                     JOIN student_courses sc ON s.student_id = sc.student_id
                     WHERE sc.course_code = c.course_code) * COUNT(DISTINCT cs.session_id) as potential_attendance,
                    (COUNT(DISTINCT a.student_id) * 100.0 / 
                        ((SELECT COUNT(DISTINCT s.student_id) 
                          FROM students s
                          JOIN student_courses sc ON s.student_id = sc.student_id
                          WHERE sc.course_code = c.course_code) * COUNT(DISTINCT cs.session_id))) as attendance_rate
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id
                {where_clause}
                GROUP BY c.course_code, time_block
                ORDER BY c.course_code, 
                    CASE time_block
                        WHEN 'Early Morning (before 9 AM)' THEN 1
                        WHEN 'Morning (9 AM - 12 PM)' THEN 2
                        WHEN 'Afternoon (12 PM - 3 PM)' THEN 3
                        WHEN 'Late Afternoon (3 PM - 6 PM)' THEN 4
                        WHEN 'Evening (after 6 PM)' THEN 5
                    END
            """
            
            return pd.read_sql_query(query, conn, params=params)
        except sqlite3.Error as e:
            print(f"Error fetching attendance by time of day: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_comparative_attendance(self, start_date=None, end_date=None):
        """Get comparative attendance data for all courses"""
        now = datetime.now()
        end_date = end_date or now.strftime("%Y-%m-%d")
        start_date = start_date or (now - timedelta(days=90)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            query = """
                SELECT 
                    c.course_code,
                    c.class_name,
                    COUNT(DISTINCT cs.session_id) as sessions_count,
                    COUNT(DISTINCT a.student_id) as total_attendance,
                    (SELECT COUNT(DISTINCT s.student_id) 
                     FROM students s
                     JOIN student_courses sc ON s.student_id = sc.student_id
                     WHERE sc.course_code = c.course_code) as total_students,
                    (COUNT(DISTINCT a.student_id) * 100.0 / 
                        ((SELECT COUNT(DISTINCT s.student_id) 
                          FROM students s
                          JOIN student_courses sc ON s.student_id = sc.student_id
                          WHERE sc.course_code = c.course_code) * COUNT(DISTINCT cs.session_id))) as attendance_rate
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id
                WHERE cs.date BETWEEN ? AND ?
                GROUP BY c.course_code, c.class_name
                ORDER BY attendance_rate DESC
            """
            
            return pd.read_sql_query(query, conn, params=(start_date, end_date))
        except sqlite3.Error as e:
            print(f"Error fetching comparative attendance: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def get_attendance_details(self, session_id):
        """Get detailed attendance data for a specific session"""
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            query = """
                SELECT 
                    s.student_id,
                    s.fname || ' ' || s.lname as student_name,
                    CASE WHEN a.id IS NULL THEN 'Absent' ELSE 'Present' END as status,
                    a.timestamp as marked_time
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN student_courses sc ON c.course_code = sc.course_code
                JOIN students s ON sc.student_id = s.student_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id AND s.student_id = a.student_id
                WHERE cs.session_id = ?
                ORDER BY student_name
            """
            
            return pd.read_sql_query(query, conn, params=(session_id,))
        except sqlite3.Error as e:
            print(f"Error fetching attendance details: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def get_session_details(self, session_id):
        """Get information about a specific session"""
        conn = self.get_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    cs.session_id,
                    cs.class_id,
                    cs.date,
                    cs.start_time,
                    cs.end_time,
                    cs.status,
                    c.course_code,
                    c.class_name,
                    i.instructor_name
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN class_instructors ci ON c.class_id = ci.class_id
                LEFT JOIN instructors i ON ci.instructor_id = i.instructor_id
                WHERE cs.session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                session_info = dict(row)
                
                # Get attendance statistics
                cursor.execute("""
                    SELECT COUNT(*) as present_count
                    FROM attendance
                    WHERE session_id = ?
                """, (session_id,))
                present_count = cursor.fetchone()["present_count"]
                
                cursor.execute("""
                    SELECT COUNT(DISTINCT s.student_id) as total_students
                    FROM students s
                    JOIN student_courses sc ON s.student_id = sc.student_id
                    WHERE sc.course_code = ?
                """, (session_info["course_code"],))
                total_students = cursor.fetchone()["total_students"]
                
                session_info["present_count"] = present_count
                session_info["total_students"] = total_students
                session_info["attendance_rate"] = (present_count / total_students * 100) if total_students > 0 else 0
                
                return session_info
            return None
        except sqlite3.Error as e:
            print(f"Error fetching session details: {e}")
            return None
        finally:
            conn.close()