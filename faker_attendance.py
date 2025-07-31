import sqlite3
import os
import random
from datetime import datetime, timedelta
import faker

# Initialize Faker
fake = faker.Faker()

class AttendanceFaker:
    def __init__(self, db_path="attendance.db"):
        """Initialize with database path"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Connect to the database
        self.connect_db()
        
        # Date range for attendance records (last 2 months)
        self.end_date = datetime(2025, 4, 28)
        self.start_date = datetime(2025, 3, 28)
        
        # Store random attendance rates by class_id
        self.class_attendance_rates = {}
        
    def connect_db(self):
        """Connect to the SQLite database"""
        if not os.path.exists(self.db_path):
            print(f"Error: Database file {self.db_path} not found.")
            return False
            
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return False
    
    def close_db(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
    
    def get_all_students(self):
        """Get all students from the database"""
        try:
            self.cursor.execute("SELECT student_id, fname, lname FROM students")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching students: {e}")
            return []
    
    def get_all_sessions(self):
        """Get all class sessions from the database"""
        try:
            # Join with classes to get more details
            self.cursor.execute("""
                SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time, 
                       c.course_code, c.class_name, c.year, c.semester
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                WHERE cs.date BETWEEN ? AND ?
                ORDER BY cs.date
            """, (self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching sessions: {e}")
            return []
    
    def get_all_classes(self):
        """Get all unique classes from the database"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT class_id, course_code, class_name
                FROM classes
            """)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching classes: {e}")
            return []
    
    def get_session_students(self, session):
        """Get students expected for a specific session based on course, year, and semester"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT s.student_id, s.fname, s.lname
                FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                WHERE sc.course_code = ?
                AND s.year_of_study = ?
                AND s.current_semester = ?
            """, (session['course_code'], session['year'], session['semester']))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching session students: {e}")
            return []
    
    def parse_time(self, time_str):
        """Parse time string in various formats to datetime.time object"""
        formats = ['%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M:%S %p']
        
        for fmt in formats:
            try:
                time_obj = datetime.strptime(time_str, fmt).time()
                return time_obj
            except ValueError:
                continue
                
        # If all formats fail, add seconds to HH:MM format and try again
        if ':' in time_str and len(time_str.split(':')) == 2:
            try:
                return datetime.strptime(f"{time_str}:00", '%H:%M:%S').time()
            except ValueError:
                pass
                
        # If everything fails, return a default time
        print(f"Warning: Could not parse time '{time_str}', using default time")
        return datetime.strptime('09:00:00', '%H:%M:%S').time()
    
    def get_students_already_marked(self, session_id):
        """Get list of student IDs already marked for this session"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT student_id FROM attendance 
                WHERE session_id = ?
            """, (session_id,))
            results = self.cursor.fetchall()
            return [row['student_id'] for row in results]
        except sqlite3.Error as e:
            print(f"Error fetching marked students: {e}")
            return []
    
    def initialize_random_attendance_rates(self, min_rate=0.70, max_rate=1.0):
        """Initialize random attendance rates for each class"""
        classes = self.get_all_classes()
        
        for class_info in classes:
            # Generate a random attendance rate between min_rate and max_rate
            # Round to 2 decimal places for readability
            rate = round(random.uniform(min_rate, max_rate), 2)
            self.class_attendance_rates[class_info['class_id']] = rate
            
        # Print the generated rates for reference
        print("\n===== Random Attendance Rates =====")
        for class_id, rate in self.class_attendance_rates.items():
            # Look up the class name for this class_id
            for class_info in classes:
                if class_info['class_id'] == class_id:
                    class_name = class_info['class_name']
                    break
            else:
                class_name = f"Class ID {class_id}"
            
            print(f"{class_name}: {rate * 100:.1f}%")
        print("==================================\n")
    
    def get_attendance_rate_for_session(self, session):
        """Get the attendance rate for a specific session based on class_id"""
        class_id = session['class_id']
        
        # If we don't have a rate for this class yet, generate one
        if class_id not in self.class_attendance_rates:
            rate = round(random.uniform(0.70, 1.0), 2)
            self.class_attendance_rates[class_id] = rate
            
        return self.class_attendance_rates[class_id]
    
    def generate_attendance(self):
        """Generate attendance records with random attendance rates per class"""
        sessions = self.get_all_sessions()
        
        if not sessions:
            print("No sessions found in the specified date range.")
            return
            
        print(f"Found {len(sessions)} sessions in the date range.")
        
        # Initialize random attendance rates for all classes
        self.initialize_random_attendance_rates()
        
        # Track statistics
        total_records = 0
        sessions_processed = 0
        
        # Process each session
        for session in sessions:
            # Get attendance rate for this session's class
            attendance_rate = self.get_attendance_rate_for_session(session)
            
            # Get students for this session
            students = self.get_session_students(session)
            
            if not students:
                print(f"No students found for session {session['session_id']} ({session['class_id']}).")
                continue
            
            # Get list of students already marked for this session
            already_marked_students = self.get_students_already_marked(session['session_id'])
            
            # Filter out students who are already marked
            eligible_students = [s for s in students if s['student_id'] not in already_marked_students]
            
            if not eligible_students:
                print(f"All students already have attendance records for session {session['session_id']}.")
                sessions_processed += 1
                continue
                
            # Generate attendance with randomness
            print(f"\nGenerating attendance for session {session['session_id']} - {session['date']} - {session['class_name']}")
            print(f"Found {len(eligible_students)} eligible students (out of {len(students)} total) for this session.")
            print(f"Using attendance rate: {attendance_rate * 100:.1f}%")
            
            # Calculate how many students should be present based on the attendance rate
            # but limit to the number of eligible students
            num_present = min(int(len(students) * attendance_rate), len(eligible_students))
            
            # Mark students as present based on attendance rate
            present_students = random.sample(eligible_students, num_present)
            
            # Create attendance records
            records_added = 0
            for student in present_students:
                # Generate a random timestamp during the session
                session_date = datetime.strptime(session['date'], "%Y-%m-%d").date()
                
                # Parse session start time with flexible format
                try:
                    session_start = self.parse_time(session['start_time'])
                    
                    # Create a session datetime object
                    session_datetime = datetime.combine(session_date, session_start)
                    
                    # Add a random offset (within 30 minutes of session start)
                    random_minutes = random.randint(0, 30)
                    attendance_time = session_datetime + timedelta(minutes=random_minutes)
                    
                    # Format the timestamp
                    timestamp = attendance_time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    try:
                        # Insert new attendance record
                        self.cursor.execute("""
                            INSERT INTO attendance (student_id, session_id, timestamp, status)
                            VALUES (?, ?, ?, 'Present')
                        """, (student['student_id'], session['session_id'], timestamp))
                        records_added += 1
                    except sqlite3.Error as e:
                        print(f"Error adding attendance record: {e}")
                except Exception as e:
                    print(f"Error processing time for session {session['session_id']}: {e}")
                    continue
            
            # Commit transaction for this session
            self.conn.commit()
            
            print(f"Added {records_added} attendance records for session {session['session_id']}")
            total_records += records_added
            sessions_processed += 1
        
        print("\n===== Summary =====")
        print(f"Processed {sessions_processed} sessions")
        print(f"Added {total_records} attendance records")
        print("===================")
    
    def run(self):
        """Run the attendance faker with random attendance rates per class"""
        print(f"Generating attendance records from {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print("Using random attendance rates per class")
        
        self.generate_attendance()
        self.close_db()
        
        print("Attendance generation complete!")


if __name__ == "__main__":
    # Configure the database path here
    DB_PATH = "attendance.db"  # Change this to your actual database path
    
    # Create and run the faker
    faker = AttendanceFaker(DB_PATH)
    faker.run()