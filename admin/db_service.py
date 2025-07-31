import sqlite3
from datetime import datetime

class DatabaseService:
    def __init__(self, db_path="attendance.db"):
        self.db_path = db_path
    
    def get_connection(self):
        """Create and return a database connection"""
        return sqlite3.connect(self.db_path)
        
    def load_settings(self):
        """Load application settings from database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT setting_key, setting_value FROM settings")
            settings = dict(cursor.fetchall())
            conn.close()
            return settings if settings else {}
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {}
    
    def save_setting(self, key, value):
        """Save a specific setting"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (setting_key, setting_value) VALUES (?, ?)", 
                (key, value)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving setting: {e}")
            return False
    
    def get_today_sessions(self):
        """Get all class sessions scheduled for today"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT 
                    cs.session_id, 
                    c.class_name, 
                    co.course_name, 
                    i.instructor_name, 
                    cs.date, 
                    cs.start_time, 
                    cs.end_time, 
                    cs.class_id, 
                    cs.status
                FROM 
                    class_sessions cs
                JOIN 
                    classes c ON cs.class_id = c.class_id
                JOIN 
                    courses co ON c.course_code = co.course_code
                LEFT JOIN 
                    class_instructors ci ON c.class_id = ci.class_id
                LEFT JOIN 
                    instructors i ON ci.instructor_id = i.instructor_id
                WHERE 
                    cs.date = ? 
                ORDER BY 
                    cs.start_time
            """, (today,))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'session_id': row[0],
                    'class_name': row[1],
                    'course_name': row[2],
                    'instructor_name': row[3] if row[3] else "No instructor",
                    'date': row[4],
                    'start_time': row[5],
                    'end_time': row[6],
                    'class_id': row[7],
                    'status': row[8]
                })
            
            conn.close()
            return sessions
        except Exception as e:
            print(f"Error getting today's sessions: {e}")
            return []
    
    def get_current_active_session(self):
        """Get current active session based on current time"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            today = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H:%M:%S")
            
            cursor.execute("""
                SELECT
                    cs.session_id, 
                    c.class_name, 
                    co.course_name, 
                    i.instructor_name, 
                    cs.date, 
                    cs.start_time, 
                    cs.end_time, 
                    cs.class_id, 
                    cs.status
                FROM 
                    class_sessions cs
                JOIN 
                    classes c ON cs.class_id = c.class_id
                JOIN 
                    courses co ON c.course_code = co.course_code
                LEFT JOIN 
                    class_instructors ci ON c.class_id = ci.class_id
                LEFT JOIN 
                    instructors i ON ci.instructor_id = i.instructor_id
                WHERE 
                    cs.date = ? AND
                    cs.start_time <= ? AND
                    (cs.end_time IS NULL OR cs.end_time >= ?) AND
                    cs.status = 'active'
                LIMIT 1
            """, (today, current_time, current_time))
            
            row = cursor.fetchone()
            if row:
                session = {
                    'session_id': row[0],
                    'class_name': row[1],
                    'course_name': row[2],
                    'instructor_name': row[3] if row[3] else "No instructor",
                    'date': row[4],
                    'start_time': row[5],
                    'end_time': row[6],
                    'class_id': row[7],
                    'status': row[8]
                }
                conn.close()
                return session
            else:
                conn.close()
                return None
        except Exception as e:
            print(f"Error getting active session: {e}")
            return None

    def create_session_record(self, class_id, date, start_time):
        """Create a new attendance session record"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Insert session details
            cursor.execute("""
                INSERT INTO class_sessions 
                (class_id, date, start_time, end_time, status) 
                VALUES (?, ?, ?, NULL, ?)
            """, (
                class_id,
                date,
                start_time,
                'active'
            ))

            session_id = cursor.lastrowid
            
            # Log activity
            cursor.execute("""
                INSERT INTO activity_log
                (user_id, activity_type, timestamp)
                VALUES (?, ?, datetime('now'))
            """, (
                "admin",  # Assuming admin user
                f"Started attendance session for class {class_id}"
            ))
            
            conn.commit()
            conn.close()
            
            return session_id
        except Exception as e:
            print(f"Error creating session record: {e}")
            return None
    
    def update_session_end_time(self, session_id):
        """Update session record with end time when attendance is stopped"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            end_time = datetime.now().strftime("%H:%M:%S")
            
            # Update session with end time and change status to 'completed'
            cursor.execute("""
                UPDATE class_sessions 
                SET end_time = ?, status = 'completed' 
                WHERE session_id = ?
            """, (end_time, session_id))
            
            # Log activity
            cursor.execute("""
                INSERT INTO activity_log
                (user_id, activity_type, timestamp)
                VALUES (?, ?, datetime('now'))
            """, (
                "admin",
                f"Ended attendance session {session_id}"
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating session end time: {e}")
            return False
    
    def mark_attendance(self, student_id, session_id):
        """Mark student attendance for a session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if attendance already marked for this student in this session
            cursor.execute("""
                SELECT id FROM attendance 
                WHERE student_id = ? AND session_id = ?
            """, (student_id, session_id))
            
            if not cursor.fetchone():
                # Insert new attendance record
                cursor.execute("""
                    INSERT INTO attendance 
                    (student_id, session_id, timestamp, status) 
                    VALUES (?, ?, ?, 'Present')
                """, (student_id, session_id, timestamp))
                
                # Log activity
                cursor.execute("""
                    INSERT INTO activity_log
                    (user_id, activity_type, timestamp)
                    VALUES (?, ?, datetime('now'))
                """, (
                    "admin",
                    f"Marked attendance for student {student_id} in session {session_id}"
                ))
                
                conn.commit()
                conn.close()
                return True
            else:
                # Already marked
                conn.close()
                return False
        except Exception as e:
            print(f"Error marking attendance: {e}")
            return False    
        
    def get_student_name(self, student_id):
        """Get student name from database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT fname, lname FROM students WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()
            conn.close()
            return f"{result[0]} {result[1]}" if result else "Unknown"
        except Exception as e:
            print(f"Error getting student name: {e}")
            return "Unknown"
        
    def get_session_students(self, session_id):
        """Get all students who should attend a specific session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # First get the class info for this session
            cursor.execute("""
                SELECT cs.class_id, c.course_code, c.year, c.semester
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                WHERE cs.session_id = ?
            """, (session_id,))
            
            session_info = cursor.fetchone()
            if not session_info:
                conn.close()
                return []
                
            class_id, course_code, year, semester = session_info
            
            # Now get all students enrolled in this course for the specific year and semester
            cursor.execute("""
                SELECT s.student_id, s.fname, s.lname
                FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                WHERE sc.course_code = ?
                AND sc.status = 'Active'
                AND (s.year_of_study = ? OR ? IS NULL OR s.year_of_study IS NULL)
                AND (s.current_semester = ? OR ? IS NULL OR s.current_semester IS NULL)
                ORDER BY s.lname, s.fname
            """, (course_code, year, year, semester, semester))
            
            students = []
            for row in cursor.fetchall():
                students.append({
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}"  # Combine fname and lname
                })
            
            conn.close()
            return students
        except Exception as e:
            print(f"Error getting session students: {e}")
            return []
            
    def get_session_attendance(self, session_id):
        """Get attendance records for a specific session"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT student_id, status, timestamp
                FROM attendance
                WHERE session_id = ?
            """, (session_id,))
            
            attendance_records = []
            for row in cursor.fetchall():
                attendance_records.append({
                    'student_id': row[0],
                    'status': row[1],
                    'timestamp': row[2]
                })
            
            conn.close()
            return attendance_records
        except Exception as e:
            print(f"Error getting session attendance: {e}")
            return []
            
    def get_expected_students(self, class_id):
        """Get list of students expected to attend a class"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get course code for the class
            cursor.execute("SELECT course_code FROM classes WHERE class_id = ?", (class_id,))
            course_code = cursor.fetchone()[0]
            
            # Get students enrolled in the course
            cursor.execute("""
                SELECT 
                    s.student_id, 
                    s.fname,
                    s.lname
                FROM 
                    students s
                JOIN 
                    student_courses sc ON s.student_id = sc.student_id
                WHERE 
                    sc.course_code = ? AND
                    sc.status = 'Active'
                ORDER BY 
                    s.lname, s.fname
            """, (course_code,))
            
            students = []
            for row in cursor.fetchall():
                students.append({
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}"  # Combine fname and lname
                })
            
            conn.close()
            return students
        except Exception as e:
            print(f"Error getting expected students: {e}")
            return []    
    def log_activity(self, user_id, activity_description):
        """Log an activity in the system"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO activity_log
                (user_id, activity_type, timestamp)
                VALUES (?, ?, datetime('now'))
            """, (user_id, activity_description))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error logging activity: {e}")
            return False
        
    def get_today_sessions_with_class_info(self):
        """Get all sessions scheduled for today along with class name and course code"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        query = """
            SELECT 
                cs.session_id, 
                cs.class_id, 
                cs.date, 
                cs.start_time, 
                cs.end_time, 
                cs.status,
                c.course_code,
                c.class_name
            FROM 
                class_sessions cs
            JOIN 
                classes c ON cs.class_id = c.class_id
            WHERE 
                cs.date = ?
            ORDER BY 
                cs.start_time
        """
        
        cursor.execute(query, (today_date,))
        sessions = []
        
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row[0],
                'class_id': row[1],
                'date': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'status': row[5],
                'course_code': row[6],
                'class_name': row[7]
            })
            
        conn.close()
        return sessions
        
    def get_current_active_session_with_class_info(self):
        """Get the currently active session with class name and course code"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().time().strftime("%H:%M:%S")
        
        query = """
            SELECT 
                cs.session_id, 
                cs.class_id, 
                cs.date, 
                cs.start_time, 
                cs.end_time, 
                cs.status,
                c.course_code,
                c.class_name
            FROM 
                class_sessions cs
            JOIN 
                classes c ON cs.class_id = c.class_id
            WHERE 
                cs.date = ? AND
                cs.start_time <= ? AND
                (cs.end_time IS NULL OR cs.end_time >= ?)
            ORDER BY 
                cs.start_time
            LIMIT 1
        """
        
        cursor.execute(query, (today_date, current_time, current_time))
        row = cursor.fetchone()
        
        active_session = None
        if row:
            active_session = {
                'session_id': row[0],
                'class_id': row[1],
                'date': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'status': row[5],
                'course_code': row[6],
                'class_name': row[7]
            }
            
        conn.close()
        return active_session

    def get_classes(self):
        """
        Get all classes from the database
        
        Returns:
            list: List of dictionaries containing class_id, class_name, course_code
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT class_id, class_name, course_code, year, semester
                FROM classes
                ORDER BY class_id
            """
            cursor.execute(query)
            
            classes = []
            for row in cursor.fetchall():
                classes.append({
                    'class_id': row[0],
                    'class_name': row[1],
                    'course_code': row[2],
                    'year': row[3],
                    'semester': row[4]
                })
            
            conn.close()
            return classes
        except Exception as e:
            print(f"Database error in get_classes: {e}")
            return []

    def get_instructors(self):
        """
        Get all instructors from the database
        
        Returns:
            list: List of dictionaries containing instructor_id, first_name, last_name
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT instructor_id, instructor_name 
                FROM instructors 
                ORDER BY instructor_name
            """
            cursor.execute(query)
            
            instructors = []
            for row in cursor.fetchall():
                # Split instructor_name into first_name and last_name
                name_parts = row[1].split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                instructors.append({
                    'instructor_id': row[0],
                    'first_name': first_name,
                    'last_name': last_name
                })
            
            conn.close()
            return instructors
        except Exception as e:
            print(f"Database error in get_instructors: {e}")
            return []

    def get_courses(self):
        """
        Get all courses from the database
        
        Returns:
            list: List of dictionaries containing course_code and course_name
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = "SELECT course_code, course_name FROM courses ORDER BY course_code"
            cursor.execute(query)
            
            courses = []
            for row in cursor.fetchall():
                courses.append({
                    'course_code': row[0],
                    'course_name': row[1]
                })
            
            conn.close()
            return courses
        except Exception as e:
            print(f"Database error in get_courses: {e}")
            return []

    def get_attendance_report(self, start_date, end_date, course_code=None, instructor_id=None, class_id=None, year_of_study=None, semester=None):
        """
        Get attendance report based on filters
        
        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            course_code (str, optional): Filter by course code
            instructor_id (int, optional): Filter by instructor ID
            class_id (str, optional): Filter by class ID
            year_of_study (int, optional): Filter by year of study
            semester (str, optional): Filter by semester
            
        Returns:
            list: List of attendance records matching the filters
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_params = [start_date, end_date]
            
            query = """
                SELECT 
                    a.id,
                    a.student_id,
                    s.fname,
                    s.lname,
                    cs.session_id,
                    cs.date,
                    cs.start_time,
                    cs.end_time,
                    c.class_name,
                    co.course_code,
                    co.course_name,
                    a.timestamp,
                    a.status
                FROM 
                    attendance a
                JOIN 
                    students s ON a.student_id = s.student_id
                JOIN 
                    class_sessions cs ON a.session_id = cs.session_id
                JOIN 
                    classes c ON cs.class_id = c.class_id
                JOIN 
                    courses co ON c.course_code = co.course_code
                LEFT JOIN 
                    class_instructors ci ON c.class_id = ci.class_id
                WHERE 
                    cs.date BETWEEN ? AND ?
            """
            
            # Add filters if provided
            if course_code:
                query += " AND co.course_code = ?"
                query_params.append(course_code)
                
            if instructor_id:
                query += " AND ci.instructor_id = ?"
                query_params.append(instructor_id)
                
            if class_id:
                query += " AND c.class_id = ?"
                query_params.append(class_id)
                
            if year_of_study:
                query += " AND s.year_of_study = ?"
                query_params.append(year_of_study)
                
            if semester:
                query += " AND s.current_semester = ?"
                query_params.append(semester)
            
            query += " ORDER BY cs.date, cs.start_time, s.lname, s.fname"
            
            cursor.execute(query, query_params)
            
            attendance_records = []
            for row in cursor.fetchall():
                attendance_records.append({
                    'id': row[0],
                    'student_id': row[1],
                    'student_name': f"{row[2]} {row[3]}",
                    'session_id': row[4],
                    'date': row[5],
                    'start_time': row[6],
                    'end_time': row[7],
                    'class_name': row[8],
                    'course_code': row[9],
                    'course_name': row[10],
                    'timestamp': row[11],
                    'status': row[12]
                })
            
            conn.close()
            return attendance_records
        except Exception as e:
            print(f"Database error in get_attendance_report: {e}")
            return []

    def get_student_attendance_summary(self, student_id=None, course_code=None, start_date=None, end_date=None):
        """
        Get attendance summary for a specific student or all students
        
        Args:
            student_id (str, optional): Filter by student ID
            course_code (str, optional): Filter by course code
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
        
        Returns:
            list: List of attendance summary records
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_params = []
            
            query = """
                SELECT 
                    s.student_id,
                    s.fname,
                    s.lname,
                    co.course_code,
                    co.course_name,
                    COUNT(DISTINCT cs.session_id) as total_sessions,
                    COUNT(a.id) as attended_sessions,
                    CASE 
                        WHEN COUNT(DISTINCT cs.session_id) = 0 THEN 0
                        ELSE CAST(COUNT(a.id) AS FLOAT) / COUNT(DISTINCT cs.session_id) * 100 
                    END as attendance_percentage
                FROM 
                    students s
                JOIN 
                    student_courses sc ON s.student_id = sc.student_id
                JOIN 
                    courses co ON sc.course_code = co.course_code
                JOIN 
                    classes c ON co.course_code = c.course_code
                JOIN 
                    class_sessions cs ON c.class_id = cs.class_id
                LEFT JOIN 
                    attendance a ON (s.student_id = a.student_id AND cs.session_id = a.session_id)
                WHERE 
                    1=1
            """
            
            # Add filters if provided
            if student_id:
                query += " AND s.student_id = ?"
                query_params.append(student_id)
                
            if course_code:
                query += " AND co.course_code = ?"
                query_params.append(course_code)
                
            if start_date:
                query += " AND cs.date >= ?"
                query_params.append(start_date)
                
            if end_date:
                query += " AND cs.date <= ?"
                query_params.append(end_date)
            
            query += """
                GROUP BY 
                    s.student_id, co.course_code
                ORDER BY 
                    s.lname, s.fname, co.course_code
            """
            
            cursor.execute(query, query_params)
            
            summaries = []
            for row in cursor.fetchall():
                summaries.append({
                    'student_id': row[0],
                    'student_name': f"{row[1]} {row[2]}",
                    'course_code': row[3],
                    'course_name': row[4],
                    'total_sessions': row[5],
                    'attended_sessions': row[6],
                    'attendance_percentage': row[7]
                })
            
            conn.close()
            return summaries
        except Exception as e:
            print(f"Database error in get_student_attendance_summary: {e}")
            return []     
           
    def get_instructor_courses(self, instructor_id):
        """
        Get all courses taught by a specific instructor
        
        Args:
            instructor_id: The ID of the instructor
            
        Returns:
            List of dictionaries containing course information
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT ic.course_code, c.course_name
                FROM instructor_courses ic
                JOIN courses c ON ic.course_code = c.course_code
                WHERE ic.instructor_id = ?
            """
            
            cursor.execute(query, (instructor_id,))
            
            # Convert results to list of dictionaries
            courses = []
            for row in cursor.fetchall():
                courses.append({
                    'course_code': row[0],
                    'course_name': row[1]
                })
            
            conn.close()
            return courses
            
        except Exception as e:
            print(f"Error getting instructor courses: {e}")
            return []
        
    def get_instructors_by_course(self, course_code):
        """
        Get all instructors teaching a specific course
        
        Args:
            course_code (str): Course code to filter by
            
        Returns:
            list: List of dictionaries containing instructor information
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    i.instructor_id, 
                    i.instructor_name
                FROM 
                    instructors i
                JOIN 
                    instructor_courses ic ON i.instructor_id = ic.instructor_id
                WHERE 
                    ic.course_code = ?
                ORDER BY 
                    i.instructor_name
            """
            
            cursor.execute(query, (course_code,))
            
            instructors = []
            for row in cursor.fetchall():
                # Split instructor_name into first_name and last_name
                name_parts = row[1].split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                instructors.append({
                    'instructor_id': row[0],
                    'first_name': first_name,
                    'last_name': last_name
                })
            
            conn.close()
            return instructors
        except Exception as e:
            print(f"Error getting instructors by course: {e}")
            return []
        
    def get_classes_by_instructor(self, instructor_id):
        """
        Get all classes taught by a specific instructor
        
        Args:
            instructor_id (int): Instructor ID to filter by
            
        Returns:
            list: List of dictionaries containing class information
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    c.class_id, 
                    c.class_name, 
                    c.course_code,
                    c.year,
                    c.semester
                FROM 
                    classes c
                JOIN 
                    class_instructors ci ON c.class_id = ci.class_id
                WHERE 
                    ci.instructor_id = ?
                ORDER BY 
                    c.class_id
            """
            
            cursor.execute(query, (instructor_id,))
            
            classes = []
            for row in cursor.fetchall():
                classes.append({
                    'class_id': row[0],
                    'class_name': row[1],
                    'course_code': row[2],
                    'year': row[3],
                    'semester': row[4]
                })
            
            conn.close()
            return classes
        except Exception as e:
            print(f"Error getting classes by instructor: {e}")
            return []
        
    def get_filtered_attendance(self, filters):
        """Get attendance records with multiple filters"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Extract filters
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        course_code = filters.get('course_code')
        class_id = filters.get('class_id')
        student_id = filters.get('student_id')
        status = filters.get('status')
        
        # Build the query with potential filters
        query = """
        SELECT 
            cs.date,
            c.course_code,
            cl.class_name,
            a.student_id,
            s.fname || ' ' || s.lname as student_name,
            a.status,
            time(a.timestamp) as time
        FROM attendance a
        JOIN class_sessions cs ON a.session_id = cs.session_id
        JOIN classes cl ON cs.class_id = cl.class_id
        JOIN courses c ON cl.course_code = c.course_code
        JOIN students s ON a.student_id = s.student_id
        WHERE cs.date BETWEEN ? AND ?
        """
        
        # Parameters for query
        params = [date_from, date_to]
        
        # Add optional filters
        if course_code:
            query += " AND c.course_code = ?"
            params.append(course_code)
        
        if class_id:
            query += " AND cl.class_id = ?"
            params.append(class_id)
        
        if student_id:
            query += " AND a.student_id LIKE ?"
            params.append(f"%{student_id}%")
        
        if status:
            query += " AND a.status = ?"
            params.append(status)
        
        # Order by date, course, class, and student
        query += " ORDER BY cs.date DESC, c.course_code, cl.class_name, s.lname, s.fname"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Convert to dictionary for easier access
        attendance_records = []
        for row in results:
            attendance_records.append({
                'date': row[0],
                'course_code': row[1],
                'class_name': row[2],
                'student_id': row[3],
                'student_name': row[4],
                'status': row[5],
                'time': row[6]
            })
        
        conn.close()
        return attendance_records
    # Add these methods to the DatabaseService class
    def get_all_courses(self):
        """Get all courses from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_code")
        results = cursor.fetchall()
        
        courses = []
        for row in results:
            courses.append({
                'course_code': row[0],
                'course_name': row[1]
            })
        
        conn.close()
        return courses

    def get_all_classes(self):
        """Get all classes from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT class_id, class_name, course_code, year, semester
            FROM classes
            ORDER BY class_id
        """)
        results = cursor.fetchall()
        
        classes = []
        for row in results:
            classes.append({
                'class_id': row[0],
                'class_name': row[1],
                'course_code': row[2],
                'year': row[3],
                'semester': row[4]
            })
        
        conn.close()
        return classes

    def get_classes_by_course(self, course_code):
        """Get classes filtered by course"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT class_id, class_name, course_code, year, semester
            FROM classes
            WHERE course_code = ?
            ORDER BY class_id
        """, (course_code,))
        results = cursor.fetchall()
        
        classes = []
        for row in results:
            classes.append({
                'class_id': row[0],
                'class_name': row[1],
                'course_code': row[2],
                'year': row[3],
                'semester': row[4]
            })
        
        conn.close()
        return classes

    
    def get_filtered_attendance(self, filters):
        """
        Get attendance data based on provided filters
        
        Args:
            filters (dict): Dictionary containing filter criteria like:
                - from_date: Start date (YYYY-MM-DD)
                - to_date: End date (YYYY-MM-DD)
                - course_code: Filter by course code
                - class_id: Filter by class ID
                - student_search: Filter by student name or ID
                - include_chart: Boolean indicating if chart data should be included
                
        Returns:
            list: List of dictionaries containing attendance records
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_params = []
            
            query = """
                SELECT 
                    a.id,
                    cs.date,
                    co.course_code,
                    c.class_name,
                    a.student_id,
                    s.fname || ' ' || s.lname as student_name,
                    a.status,
                    a.timestamp
                FROM 
                    attendance a
                JOIN 
                    class_sessions cs ON a.session_id = cs.session_id
                JOIN 
                    classes c ON cs.class_id = c.class_id
                JOIN 
                    courses co ON c.course_code = co.course_code
                JOIN 
                    students s ON a.student_id = s.student_id
                WHERE 
                    1=1
            """
            
            # Add date range filters
            if filters.get('from_date'):
                query += " AND cs.date >= ?"
                query_params.append(filters['from_date'])
                
            if filters.get('to_date'):
                query += " AND cs.date <= ?"
                query_params.append(filters['to_date'])
                
            # Add course filter
            if filters.get('course_code'):
                query += " AND co.course_code = ?"
                query_params.append(filters['course_code'])
                
            # Add class filter
            if filters.get('class_id'):
                query += " AND c.class_id = ?"
                query_params.append(filters['class_id'])
                
            # Add student search filter
            if filters.get('student_search'):
                search_term = f"%{filters['student_search']}%"
                query += """ AND (
                    a.student_id LIKE ? OR
                    s.fname || ' ' || s.lname LIKE ?
                )"""
                query_params.append(search_term)
                query_params.append(search_term)
            
            # Add ordering
            query += " ORDER BY cs.date, co.course_code, c.class_name, s.lname, s.fname"
            
            cursor.execute(query, query_params)
            
            # Convert results to list of dictionaries
            attendance_records = []
            for row in cursor.fetchall():
                attendance_records.append({
                    'id': row[0],
                    'date': row[1],
                    'course_code': row[2],
                    'class_name': row[3],
                    'student_id': row[4],
                    'name': row[5],
                    'status': row[6],
                    'timestamp': row[7]
                })
            
            conn.close()
            return attendance_records
            
        except Exception as e:
            print(f"Error getting filtered attendance: {e}")
            return []
            
    def get_filtered_classes(self, instructor_id=None, year=None):
        """
        Get classes filtered by instructor and/or year of study
        
        Args:
            instructor_id (int, optional): Filter by instructor ID
            year (int, optional): Filter by year of study
            
        Returns:
            list: List of dictionaries containing class information
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_params = []
            
            query = """
                SELECT 
                    c.class_id, 
                    c.class_name, 
                    c.course_code,
                    c.year,
                    c.semester
                FROM 
                    classes c
                WHERE 
                    1=1
            """
            
            # Add filters if provided
            if instructor_id:
                query += """
                    AND c.class_id IN (
                        SELECT class_id
                        FROM class_instructors
                        WHERE instructor_id = ?
                    )
                """
                query_params.append(instructor_id)
                
            if year:
                query += " AND c.year = ?"
                query_params.append(year)
            
            query += " ORDER BY c.class_id"
            
            cursor.execute(query, query_params)
            
            classes = []
            for row in cursor.fetchall():
                classes.append({
                    'class_id': row[0],
                    'class_name': row[1],
                    'course_code': row[2],
                    'year': row[3],
                    'semester': row[4]
                })
            
            conn.close()
            return classes
        except Exception as e:
            print(f"Error getting filtered classes: {e}")
            return []
        
    def get_classes_by_course(self, course_code):
        """
        Retrieve all classes associated with a specific course.
        
        Args:
            course_code (str): The course code to filter classes by
            
        Returns:
            list: A list of dictionaries containing class information
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT class_id, class_name 
                FROM classes 
                WHERE course_code = ?
                ORDER BY year, semester, class_name
            """
            
            cursor.execute(query, (course_code,))
            
            # Fetch results and convert to list of dictionaries
            classes = []
            for row in cursor.fetchall():
                classes.append({
                    'class_id': row[0],
                    'class_name': row[1]
                })
                
            conn.close()
            return classes
            
        except Exception as e:
            print(f"Error getting classes by course: {str(e)}")
            return []