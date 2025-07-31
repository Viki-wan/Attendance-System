import sqlite3
from datetime import datetime

class AttendanceReportService:
    def __init__(self):
        self.conn = sqlite3.connect('attendance.db')
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def get_all_courses(self):
        """Get all courses from the database"""
        self.cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_code")
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_all_classes(self):
        """Get all classes from the database"""
        self.cursor.execute("""
            SELECT c.class_id, c.class_name, c.course_code, c.year, c.semester 
            FROM classes c
            ORDER BY c.class_id
        """)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_classes_by_course(self, course_code):
        """Get classes for a specific course"""
        self.cursor.execute("""
            SELECT c.class_id, c.class_name, c.course_code, c.year, c.semester 
            FROM classes c
            WHERE c.course_code = ?
            ORDER BY c.class_id
        """, (course_code,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_all_students(self):
        """Get all students from the database"""
        self.cursor.execute("""
            SELECT student_id, fname || ' ' || lname AS name, course, year_of_study, current_semester
            FROM students
            ORDER BY student_id
        """)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_filtered_attendance(self, date_from=None, date_to=None, course=None, 
                              class_id=None, student_id=None, status=None, 
                              include_absent=False, year=None):
        """
        Get filtered attendance records, including absentees if requested.
        If include_absent is True, students with no attendance record for a session are shown as 'Absent'.
        """
        query = """
            SELECT 
                s.student_id,
                s.fname || ' ' || s.lname AS student_name,
                cs.class_id,
                c.class_name,
                c.course_code,
                cs.date,
                cs.start_time AS time,
                COALESCE(a.status, 'Absent') AS status,
                s.year_of_study
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.class_id
            JOIN student_courses sc ON c.course_code = sc.course_code
            JOIN students s ON sc.student_id = s.student_id
            LEFT JOIN attendance a 
                ON a.student_id = s.student_id AND a.session_id = cs.session_id
            WHERE 1=1
        """
        params = []

        if date_from:
            query += " AND cs.date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND cs.date <= ?"
            params.append(date_to)
        if course:
            query += " AND c.course_code = ?"
            params.append(course)
        if class_id:
            query += " AND cs.class_id = ?"
            params.append(class_id)
        if student_id:
            query += " AND s.student_id = ?"
            params.append(student_id)
        if year:
            query += " AND s.year_of_study = ?"
            params.append(year)
        if status:
            query += " AND COALESCE(a.status, 'Absent') = ?"
            params.append(status)
        if not include_absent:
            query += " AND a.status = 'Present'"

        query += " ORDER BY cs.date DESC, cs.start_time DESC"

        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def group_by_date(self, attendance_data):
        """Group attendance data by date"""
        grouped_data = {}
        
        for record in attendance_data:
            date = record['date']
            if date not in grouped_data:
                grouped_data[date] = {
                    'date': date,
                    'present_count': 0,
                    'absent_count': 0,
                    'records': []
                }
            
            if record['status'] == 'Present':
                grouped_data[date]['present_count'] += 1
            else:
                grouped_data[date]['absent_count'] += 1
                
            grouped_data[date]['records'].append(record)
        
        return list(grouped_data.values())
    
    def group_by_class(self, attendance_data):
        """Group attendance data by class"""
        grouped_data = {}
        
        for record in attendance_data:
            class_id = record['class_id']
            if class_id not in grouped_data:
                grouped_data[class_id] = {
                    'class_id': class_id,
                    'class_name': record['class_name'],
                    'course_code': record['course_code'],
                    'present_count': 0,
                    'absent_count': 0,
                    'records': []
                }
            
            if record['status'] == 'Present':
                grouped_data[class_id]['present_count'] += 1
            else:
                grouped_data[class_id]['absent_count'] += 1
                
            grouped_data[class_id]['records'].append(record)
        
        return list(grouped_data.values())
    
    def generate_student_wise_report(self, date_from=None, date_to=None, 
                                   course=None, class_id=None, year=None, include_absent=True):
        """Generate a student-wise attendance report"""
        # Get all students based on filters
        query = """
            SELECT DISTINCT 
                s.student_id,
                s.fname || ' ' || s.lname as name,
                c.class_id,
                c.class_name,
                c.course_code,
                s.year_of_study
            FROM students s
            JOIN student_courses sc ON s.student_id = sc.student_id
            JOIN classes c ON sc.course_code = c.course_code
            WHERE 1=1
        """
        params = []
        
        if course:
            query += " AND c.course_code = ?"
            params.append(course)
            
        if class_id:
            query += " AND c.class_id = ?"
            params.append(class_id)
            
        if year:
            query += " AND s.year_of_study = ?"
            params.append(year)
            
        self.cursor.execute(query, params)
        students = [dict(row) for row in self.cursor.fetchall()]
        
        # Get attendance data for each student
        report_data = []
        for student in students:
            attendance_data = self.get_filtered_attendance(
                date_from, date_to, course, student['class_id'],
                student['student_id'], None, include_absent, year
            )
            
            if attendance_data:
                present_count = sum(1 for r in attendance_data if r['status'] == 'Present')
                absent_count = sum(1 for r in attendance_data if r['status'] == 'Absent')
                total_sessions = present_count + absent_count
                attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0
                
                # Calculate monthly attendance
                monthly_attendance = {}
                for record in attendance_data:
                    month = datetime.strptime(record['date'], '%Y-%m-%d').strftime('%Y-%m')
                    if month not in monthly_attendance:
                        monthly_attendance[month] = {'present': 0, 'absent': 0}
                    
                    if record['status'] == 'Present':
                        monthly_attendance[month]['present'] += 1
                    else:
                        monthly_attendance[month]['absent'] += 1
                
                report_data.append({
                    'student_id': student['student_id'],
                    'name': student['name'],
                    'course_code': student['course_code'],
                    'class_name': student['class_name'],
                    'year_of_study': student['year_of_study'],
                    'present_count': present_count,
                    'absent_count': absent_count,
                    'total_sessions': total_sessions,
                    'attendance_rate': attendance_rate,
                    'attendance_records': attendance_data,
                    'monthly_attendance': [
                        {'month': month, **data}
                        for month, data in sorted(monthly_attendance.items())
                    ]
                })
        
        return report_data
    
    def generate_class_wise_report(self, date_from=None, date_to=None, 
                                 course=None, class_id=None, year=None, include_absent=True):
        """Generate a class-wise attendance report"""
        # Get all classes based on filters
        query = """
            SELECT DISTINCT 
                c.class_id,
                c.class_name,
                c.course_code
            FROM classes c
            WHERE 1=1
        """
        params = []
        
        if course:
            query += " AND c.course_code = ?"
            params.append(course)
            
        if class_id:
            query += " AND c.class_id = ?"
            params.append(class_id)
            
        self.cursor.execute(query, params)
        classes = [dict(row) for row in self.cursor.fetchall()]
        
        # Get attendance data for each class
        report_data = []
        for class_item in classes:
            # Get all students in the class
            students_query = """
                SELECT DISTINCT s.student_id, s.fname || ' ' || s.lname as name, s.year_of_study
                FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                WHERE sc.course_code = ?
            """
            if year:
                students_query += " AND s.year_of_study = ?"
                self.cursor.execute(students_query, [class_item['course_code'], year])
            else:
                self.cursor.execute(students_query, [class_item['course_code']])
            students = [dict(row) for row in self.cursor.fetchall()]
            
            # Get attendance data for the class
            attendance_data = self.get_filtered_attendance(
                date_from, date_to, class_item['course_code'],
                class_item['class_id'], None, None, include_absent, year
            )
            
            if attendance_data:
                # Group attendance by session
                sessions = {}
                for record in attendance_data:
                    session_key = f"{record['date']}_{record['time']}"
                    if session_key not in sessions:
                        sessions[session_key] = {
                            'date': record['date'],
                            'time': record['time'],
                            'present_count': 0,
                            'absent_count': 0
                        }
                    
                    if record['status'] == 'Present':
                        sessions[session_key]['present_count'] += 1
                    else:
                        sessions[session_key]['absent_count'] += 1
                
                # Calculate student attendance
                student_attendance = {}
                for student in students:
                    student_records = [r for r in attendance_data if r['student_id'] == student['student_id']]
                    present_count = sum(1 for r in student_records if r['status'] == 'Present')
                    absent_count = sum(1 for r in student_records if r['status'] == 'Absent')
                    total_sessions = present_count + absent_count
                    
                    if total_sessions > 0:
                        student_attendance[student['student_id']] = {
                            'student_id': student['student_id'],
                            'name': student['name'],
                            'year_of_study': student['year_of_study'],
                            'present_count': present_count,
                            'absent_count': absent_count
                        }
                
                # Calculate class average attendance
                total_present = sum(s['present_count'] for s in sessions.values())
                total_absent = sum(s['absent_count'] for s in sessions.values())
                total_sessions = total_present + total_absent
                average_attendance = (total_present / total_sessions * 100) if total_sessions > 0 else 0
                
                report_data.append({
                    'class_id': class_item['class_id'],
                    'class_name': class_item['class_name'],
                    'course_code': class_item['course_code'],
                    'total_students': len(students),
                    'total_sessions': len(sessions),
                    'average_attendance': average_attendance,
                    'sessions': sorted(sessions.values(), key=lambda x: (x['date'], x['time'])),
                    'students': sorted(student_attendance.values(), key=lambda x: x['name'])
                })
        
        return report_data
    
    def get_classes_by_course_and_year(self, course_code=None, year=None):
        query = "SELECT class_id, class_name, course_code, year, semester FROM classes WHERE 1=1"
        params = []
        if course_code:
            query += " AND course_code = ?"
            params.append(course_code)
        if year:
            query += " AND year = ?"
            params.append(year)
        query += " ORDER BY class_id"
        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]