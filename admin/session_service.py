from datetime import datetime, timedelta
from admin.db_service import DatabaseService

class SessionService:
    def __init__(self, db_service=None):
        self.db_service = db_service or DatabaseService()
    
    def get_today_sessions(self):
        """Get all class sessions scheduled for today with class name and code"""
        return self.db_service.get_today_sessions_with_class_info()
    
    def get_current_active_session(self):
        """Get the current active session based on time with class info"""
        return self.db_service.get_current_active_session_with_class_info()
    
    def filter_sessions_by_time(self, sessions):
        """Filter sessions based on current time
        
        Returns:
            tuple: (current_sessions, upcoming_sessions)
                - current_sessions: Sessions currently in progress
                - upcoming_sessions: Sessions starting within the next 5 minutes
        """
        current_time = datetime.now().time()
        current_time_str = current_time.strftime("%H:%M:%S")
        
        current_sessions = []
        for session in sessions:
            start_time = session['start_time']
            end_time = session['end_time']
            
            # If end_time is None or "End", consider session active if after start time
            if start_time <= current_time_str and (not end_time or end_time == "End" or current_time_str <= end_time):
                current_sessions.append(session)
        
        # Get upcoming sessions (starting within next 5 minutes)
        upcoming_sessions = self.get_upcoming_sessions(sessions, minutes=5)
        
        return current_sessions, upcoming_sessions

    def get_upcoming_sessions(self, sessions, minutes=5):
        """Get sessions starting within the specified minutes from now"""
        current_time = datetime.now()
        
        # Calculate time X minutes from now
        future_time = current_time + timedelta(minutes=minutes)
        
        upcoming_sessions = []
        for session in sessions:
            start_time_str = session['start_time']
            
            # Parse the session start time
            try:
                # Assuming start_time is in format "HH:MM:SS"
                hour, minute, second = map(int, start_time_str.split(':'))
                session_time = current_time.replace(hour=hour, minute=minute, second=second)
                
                # If the session time is earlier in the day but we're past that time, it's not upcoming
                if session_time < current_time:
                    continue
                    
                # Check if within specified minutes
                if session_time <= future_time:
                    upcoming_sessions.append(session)
            except:
                continue
        
        return upcoming_sessions
    
    def is_session_starting_soon(self, session, minutes=5):
        """Check if a session is starting within the specified minutes"""
        if not session or 'start_time' not in session:
            return False
        
        current_time = datetime.now()
        start_time_str = session['start_time']
        
        # Parse the session start time
        try:
            # Assuming start_time is in format "HH:MM:SS"
            hour, minute, second = map(int, start_time_str.split(':'))
            session_time = current_time.replace(hour=hour, minute=minute, second=second)
            
            # If the session time is earlier in the day but we're past that time, it's not soon
            if session_time < current_time:
                return False
                
            # Check if within specified minutes
            time_until_start = session_time - current_time
            return time_until_start <= timedelta(minutes=minutes)
        except:
            return False
    
    def is_session_valid_for_attendance(self, session):
        """Check if a session is valid for attendance (in progress or starting within 5 minutes)"""
        if not session:
            return False
            
        # Check if session is already in progress
        current_time = datetime.now().time()
        current_time_str = current_time.strftime("%H:%M:%S")
        start_time = session['start_time']
        end_time = session['end_time']
        
        # Session is in progress
        if start_time <= current_time_str and (not end_time or end_time == "End" or current_time_str <= end_time):
            return True
            
        # Session is about to start within 5 minutes
        return self.is_session_starting_soon(session, 5)
    
    def get_active_or_upcoming_sessions(self):
        """Get sessions that are either currently active or starting within 5 minutes"""
        all_sessions = self.get_today_sessions()
        current_sessions, upcoming_sessions = self.filter_sessions_by_time(all_sessions)
        
        # Combine current and upcoming sessions
        return current_sessions + upcoming_sessions
    
    def format_session_display(self, session):
        """Format the session display text to include class code and name"""
        class_code = session.get('course_code', '')
        class_name = session.get('class_name', '')
        start_time = session.get('start_time', '').split(':')[:2]  # Get only hours and minutes
        
        # Format start time as HH:MM
        formatted_time = ':'.join(start_time) if len(start_time) >= 2 else ''
        
        # Check if session is currently active or upcoming
        status = ""
        if self.is_session_starting_soon(session, 5) and not self.is_session_valid_for_attendance(session):
            status = " (Starting Soon)"
        elif self.is_session_valid_for_attendance(session):
            status = " (In Progress)"
            
        # Create display text
        if class_code and class_name:
            return f"{class_code} - {class_name} | {formatted_time}{status}"
        elif class_code:
            return f"{class_code} | {formatted_time}{status}"
        elif class_name:
            return f"{class_name} | {formatted_time}{status}"
        else:
            return f"Class Session | {formatted_time}{status}"
    
    def get_formatted_active_or_upcoming_sessions(self):
        """Get active or upcoming sessions with formatted display values"""
        sessions = self.get_active_or_upcoming_sessions()
        
        # Add a display_text field to each session
        for session in sessions:
            session['display_text'] = self.format_session_display(session)
            
        return sessions
    
    def create_session_record(self, class_id, date, start_time):
        """Create a new attendance session record"""
        return self.db_service.create_session_record(class_id, date, start_time)
    
    def end_session(self, session_id):
        """End an active session"""
        return self.db_service.update_session_end_time(session_id)
    
    def get_students_for_session(self, class_id):
        """Get students registered for a specific class session"""
        return self.db_service.get_expected_students(class_id)
    
    def filter_students_by_enrollment(self, students, course_code, year=None, semester=None):
        """Filter students based on enrollment criteria"""
        if not course_code:
            return students
            
        conn = self.db_service.get_connection()
        cursor = conn.cursor()
        
        filtered_students = []
        for student in students:
            student_id = student['student_id']
            
            # Build the query based on provided filters
            query = "SELECT 1 FROM student_courses WHERE student_id = ? AND course_code = ?"
            params = [student_id, course_code]
            
            if semester:
                query += " AND semester = ?"
                params.append(semester)
                
            # For year, we need to check the students table
            if year:
                query = f"""
                    SELECT 1 FROM student_courses sc
                    JOIN students s ON sc.student_id = s.student_id
                    WHERE sc.student_id = ? AND sc.course_code = ? 
                    AND s.year_of_study = ?
                """
                params = [student_id, course_code, year]
                
                if semester:
                    query += " AND sc.semester = ?"
                    params.append(semester)
            
            cursor.execute(query, params)
            if cursor.fetchone():
                filtered_students.append(student)
        
        conn.close()
        return filtered_students