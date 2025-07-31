# db_attendance_service.py
import sqlite3
import os
from datetime import datetime, timedelta

class DatabaseAttendanceService:
    """Database service specifically for attendance reporting functionality"""
    
    def __init__(self, db_path='database.db'):
        self.db_path = db_path
    
    def get_connection(self):
        """Get SQLite database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_filtered_attendance(self, filters):
        """
        Get attendance records with applied filters
        
        Args:
            filters (dict): Dictionary containing filter criteria
                - from_date: Start date for filtering
                - to_date: End date for filtering
                - course_code: Course code filter (optional)
                - class_id: Class ID filter (optional)
                - student_search: Student ID or name search term (optional)
                
        Returns:
            list: List of attendance records matching the filters
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build base query
        query = """
            SELECT 
                cs.date,
                c.course_code,
                c.class_name,
                a.student_id,
                s.fname || ' ' || s.lname as name,
                a.status,
                a.timestamp
            FROM attendance a
            JOIN class_sessions cs ON a.session_id = cs.session_id
            JOIN classes c ON cs.class_id = c.class_id
            JOIN students s ON a.student_id = s.student_id
            WHERE cs.date BETWEEN ? AND ?
        """
        
        # Start with basic date parameters
        params = [filters['from_date'], filters['to_date']]
        
        # Add course filter if specified
        if filters.get('course_code'):
            query += " AND c.course_code = ?"
            params.append(filters['course_code'])
        
        # Add class filter if specified
        if filters.get('class_id'):
            query += " AND c.class_id = ?"
            params.append(filters['class_id'])
        
        # Add student search if specified
        if filters.get('student_search'):
            search_term = f"%{filters['student_search']}%"
            query += " AND (a.student_id LIKE ? OR s.fname LIKE ? OR s.lname LIKE ?)"
            params.extend([search_term, search_term, search_term])
        
        # Add sorting
        query += " ORDER BY cs.date DESC, cs.start_time DESC, s.lname, s.fname"
        
        # Execute query
        cursor.execute(query, params)
        result = cursor.fetchall()
        
        # Convert to list of dictionaries
        columns = [col[0] for col in cursor.description]
        attendance_records = []
        for row in result:
            record = dict(zip(columns, row))
            attendance_records.append(record)
        
        cursor.close()
        conn.close()
        
        return attendance_records
    
    def get_all_courses(self):
        """Get all courses from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_code")
        result = cursor.fetchall()
        
        # Convert to list of dictionaries
        courses = [{'course_code': row[0], 'course_name': row[1]} for row in result]
        
        cursor.close()
        conn.close()
        
        return courses
    
    def get_all_classes(self):
        """Get all classes from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT class_id, class_name, course_code 
            FROM classes 
            ORDER BY class_id
        """)
        result = cursor.fetchall()
        
        # Convert to list of dictionaries
        classes = [{'class_id': row[0], 'class_name': row[1], 'course_code': row[2]} for row in result]
        
        cursor.close()
        conn.close()
        
        return classes
    
    def get_classes_by_course(self, course_code):
        """Get classes for a specific course"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT class_id, class_name, course_code 
            FROM classes 
            WHERE course_code = ?
            ORDER BY class_id
        """, (course_code,))
        result = cursor.fetchall()
        
        # Convert to list of dictionaries
        classes = [{'class_id': row[0], 'class_name': row[1], 'course_code': row[2]} for row in result]
        
        cursor.close()
        conn.close()
        
        return classes
    
    def get_attendance_statistics(self, filters):
        """
        Get attendance statistics based on filters
        
        Args:
            filters (dict): Dictionary containing filter criteria
                
        Returns:
            dict: Statistics including total sessions, attendance rate, etc.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get total number of sessions
        session_query = """
            SELECT COUNT(DISTINCT cs.session_id) 
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.class_id
            WHERE cs.date BETWEEN ? AND ?
        """
        
        session_params = [filters['from_date'], filters['to_date']]
        
        if filters.get('course_code'):
            session_query += " AND c.course_code = ?"
            session_params.append(filters['course_code'])
        
        if filters.get('class_id'):
            session_query += " AND c.class_id = ?"
            session_params.append(filters['class_id'])
        
        cursor.execute(session_query, session_params)
        total_sessions = cursor.fetchone()[0]
        
        # Get total enrolled students
        student_query = """
            SELECT COUNT(DISTINCT sc.student_id)
            FROM student_courses sc
            JOIN classes c ON sc.course_code = c.course_code
            WHERE 1=1
        """
        
        student_params = []
        
        if filters.get('course_code'):
            student_query += " AND c.course_code = ?"
            student_params.append(filters['course_code'])
        
        if filters.get('class_id'):
            student_query += " AND c.class_id = ?"
            student_params.append(filters['class_id'])
        
        cursor.execute(student_query, student_params)
        total_students = cursor.fetchone()[0]
        
        # Get attendance data by date
        attendance_query = """
            SELECT 
                cs.date, 
                COUNT(DISTINCT a.student_id) as present_count,
                (SELECT COUNT(DISTINCT sc.student_id) 
                 FROM student_courses sc 
                 JOIN classes cl ON sc.course_code = cl.course_code
                 WHERE cl.class_id = cs.class_id) as total_count
            FROM class_sessions cs
            LEFT JOIN attendance a ON cs.session_id = a.session_id
            JOIN classes c ON cs.class_id = c.class_id
            WHERE cs.date BETWEEN ? AND ?
        """
        
        attendance_params = [filters['from_date'], filters['to_date']]
        
        if filters.get('course_code'):
            attendance_query += " AND c.course_code = ?"
            attendance_params.append(filters['course_code'])
        
        if filters.get('class_id'):
            attendance_query += " AND c.class_id = ?"
            attendance_params.append(filters['class_id'])
        
        attendance_query += " GROUP BY cs.date ORDER BY cs.date"
        
        cursor.execute(attendance_query, attendance_params)
        attendance_by_date = cursor.fetchall()
        
        # Calculate average attendance rate
        total_present = 0
        total_expected = 0
        attendance_data = []
        
        for date, present, expected in attendance_by_date:
            if expected > 0:
                rate = round((present / expected) * 100, 1)
            else:
                rate = 0
                
            total_present += present
            total_expected += expected
            
            attendance_data.append({
                'date': date,
                'present': present,
                'expected': expected,
                'rate': rate
            })
        
        # Calculate overall attendance rate
        if total_expected > 0:
            attendance_rate = round((total_present / total_expected) * 100, 1)
        else:
            attendance_rate = 0
        
        cursor.close()
        conn.close()
        
        return {
            'total_sessions': total_sessions,
            'total_students': total_students,
            'attendance_rate': attendance_rate,
            'attendance_data': attendance_data
        }