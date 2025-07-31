import sqlite3
import sys
import os
import random
import re
from datetime import datetime, timedelta, date
from faker import Faker
from PyQt5.QtCore import QDate, QTime

# Set up the faker
fake = Faker()

# Database path - adjust as needed
DATABASE_PATH = "path/to/your/database.db"  # Update this path

def get_database_path():
    """Get the actual database path from settings or use the default"""
    try:
        # Try to import from your config
        from config.utils_constants import DATABASE_PATH
        return DATABASE_PATH
    except ImportError:
        print("Could not import DATABASE_PATH from config, using default path")
        return DATABASE_PATH

def determine_current_semester():
    """Determine the current semester based on today's date"""
    today = date.today()
    month = today.month
    
    # Determine semester from month
    if 9 <= month <= 12:
        # First semester (September to December)
        return 1
    elif 1 <= month <= 4:
        # Second semester (January to April)
        return 2
    else:
        # Default to first semester during break months
        return 1

def get_semester_date_range():
    """Get the date range for the current semester"""
    today = date.today()
    year = today.year
    current_semester = determine_current_semester()
    
    if current_semester == 1:  # First semester
        # September to December
        semester_start = date(year, 9, 1)
        semester_end = date(year, 12, 31)
    else:  # Second semester
        # January to April
        semester_start = date(year, 1, 10)  # After winter break
        semester_end = date(year, 4, 30)
    
    # If we're before the start of the current semester, adjust to previous semester
    if today < semester_start:
        if current_semester == 1:  # If we're before first semester, look at second semester of previous year
            semester_start = date(year - 1, 1, 10)
            semester_end = date(year - 1, 4, 30)
        else:  # If we're before second semester, look at first semester
            semester_start = date(year - 1, 9, 1)
            semester_end = date(year - 1, 12, 31)
    
    # If we're during a break period, adjust to the upcoming semester
    if not (semester_start <= today <= semester_end):
        month = today.month
        if 5 <= month <= 8:  # Summer break, prepare for first semester
            semester_start = date(year, 9, 1)
            semester_end = date(year, 12, 31)
    
    print(f"Generating sessions for semester period: {semester_start} to {semester_end}")
    return semester_start, semester_end

def determine_status(session_date, start_time, end_time):
    """Automatically determine session status based on date and time"""
    today = datetime.now().date()
    current_time = datetime.now().time()
    
    # Convert string times to time objects if needed
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%H:%M").time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%H:%M").time()
            
    # If the session date is in the future
    if session_date > today:
        return "scheduled"
    
    # If the session date is today
    elif session_date == today:
        # If the session hasn't started yet
        if current_time < start_time:
            return "scheduled"
        # If the session is currently happening
        elif start_time <= current_time <= end_time:
            return "in-progress"
        # If the session has ended
        else:
            return "completed"
    
    # If the session date is in the past
    else:
        return "completed"

def check_scheduling_conflicts(conn, course_code, year, semester, date_str, start_time, end_time, session_id=None):
    """
    Check for scheduling conflicts with other classes in the same course/semester
    Returns a list of conflicts if any exist
    """
    cursor = conn.cursor()
    
    query = """
        SELECT cs.session_id, c.class_name, cs.start_time, cs.end_time
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        WHERE c.course_code = ? AND c.year = ? AND c.semester = ?
        AND cs.date = ?
        AND ((cs.start_time < ? AND cs.end_time > ?) OR
            (cs.start_time >= ? AND cs.start_time < ?) OR
            (cs.end_time > ? AND cs.end_time <= ?))
    """
    
    params = (course_code, year, semester, date_str, 
              end_time, start_time, start_time, end_time, start_time, end_time)
    
    # If we're checking against an existing session, exclude it from the conflict check
    if session_id:
        query += " AND cs.session_id != ?"
        params += (session_id,)
    
    cursor.execute(query, params)
    return cursor.fetchall()

def get_classes_for_current_semester(conn):
    """Get classes for the current semester"""
    cursor = conn.cursor()
    
    # Determine current semester
    current_semester_num = determine_current_semester()
    
    # Get current year
    current_year = datetime.now().year
    
    # Query classes for the current semester
    # Format semester as "year.semester_num"
    cursor.execute("""
        SELECT class_id, class_name, course_code, year, semester 
        FROM classes 
        WHERE semester LIKE ?
    """, (f"%.{current_semester_num}",))
    
    return cursor.fetchall()

def generate_class_sessions():
    """Generate random class sessions for all classes in the current semester"""
    try:
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get semester date range
        semester_start, semester_end = get_semester_date_range()
        
        # Get classes for the current semester
        classes = get_classes_for_current_semester(conn)
        
        if not classes:
            print("No classes found for the current semester")
            conn.close()
            return
        
        print(f"Found {len(classes)} classes for the current semester")
        
        # Define time slots (common class hours)
        time_slots = [
            ("08:00", "10:00"),  # Morning classes
            ("10:15", "12:15"),  # Late morning
            ("13:00", "15:00"),  # Early afternoon
            ("15:15", "17:15"),  # Late afternoon
            ("18:00", "20:00"),  # Evening classes
        ]
        
        # Standard weekdays (Monday-Friday)
        weekdays = [0, 1, 2, 3, 4]  # 0=Monday, 4=Friday
        
        print(f"Generating sessions from {semester_start} to {semester_end}")
        
        # Keep track of total sessions created and conflicts
        total_sessions = 0
        total_conflicts = 0
        
        # Process each class
        for class_id, class_name, course_code, year, semester in classes:
            print(f"Processing class: {class_name} (ID: {class_id}, Semester: {semester})")
            
            # For each class, select 2-3 random weekdays for sessions
            class_days = random.sample(weekdays, min(random.randint(2, 3), len(weekdays)))
            
            # Select 1-2 time slots for this class
            num_time_slots = random.randint(1, 2)
            class_time_slots = random.sample(time_slots, num_time_slots)
            
            # Generate sessions for this class
            class_sessions = 0
            class_conflicts = 0
            
            # Start from semester start date
            current_date = semester_start
            
            # Generate sessions until semester end
            while current_date <= semester_end:
                # Check if the current weekday matches one of our class days
                if current_date.weekday() in class_days:
                    for start_time, end_time in class_time_slots:
                        date_str = current_date.strftime("%Y-%m-%d")
                        
                        # Check for scheduling conflicts
                        conflicts = check_scheduling_conflicts(
                            conn, course_code, year, semester, 
                            date_str, start_time, end_time
                        )
                        
                        if conflicts:
                            class_conflicts += 1
                            continue
                        
                        # No conflicts, insert the session
                        status = determine_status(current_date, start_time, end_time)
                        
                        try:
                            # Insert the session
                            cursor.execute("""
                                INSERT INTO class_sessions 
                                (class_id, date, start_time, end_time, status) 
                                VALUES (?, ?, ?, ?, ?)
                            """, (class_id, date_str, start_time, end_time, status))
                            
                            class_sessions += 1
                        except sqlite3.IntegrityError:
                            # Skip if this session already exists
                            pass
                
                # Move to next day
                current_date += timedelta(days=1)
            
            print(f"Created {class_sessions} sessions for {class_name} (Skipped {class_conflicts} due to conflicts)")
            total_sessions += class_sessions
            total_conflicts += class_conflicts
        
        # Commit all changes
        conn.commit()
        print(f"\nTotal sessions created: {total_sessions}")
        print(f"Total sessions skipped due to conflicts: {total_conflicts}")
        
        # Optional: Generate some random past attendance data
        generate_random_attendance = input("Generate random attendance data for past sessions? (y/n): ")
        if generate_random_attendance.lower() == 'y':
            generate_attendance_data(conn)
        
        conn.close()
        print("Done!")
        
    except Exception as e:
        print(f"Error generating class sessions: {e}")
        if 'conn' in locals():
            conn.close()

def generate_attendance_data(conn):
    """Generate random attendance data for past sessions"""
    cursor = conn.cursor()
    
    # Get all completed sessions
    cursor.execute("""
        SELECT session_id, class_id 
        FROM class_sessions 
        WHERE status = 'completed'
    """)
    completed_sessions = cursor.fetchall()
    
    if not completed_sessions:
        print("No completed sessions found")
        return
        
    print(f"Generating attendance data for {len(completed_sessions)} completed sessions")
    
    # Track attendance records created
    attendance_count = 0
    
    # Process each completed session
    for session_id, class_id in completed_sessions:
        # Get students for this class's course
        cursor.execute("""
            SELECT s.student_id 
            FROM students s
            JOIN student_courses sc ON s.student_id = sc.student_id
            JOIN classes c ON sc.course_code = c.course_code
            WHERE c.class_id = ?
        """, (class_id,))
        
        students = cursor.fetchall()
        
        if not students:
            continue
            
        # For each student, decide attendance status
        for (student_id,) in students:
            # 85% chance of being present
            status = random.choices(
                ['Present', 'Absent', 'Late'], 
                weights=[85, 10, 5], 
                k=1
            )[0]
            
            try:
                # Create timestamp within the session time
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Insert attendance record
                cursor.execute("""
                    INSERT INTO attendance 
                    (student_id, session_id, timestamp, status) 
                    VALUES (?, ?, ?, ?)
                """, (student_id, session_id, timestamp, status))
                
                attendance_count += 1
            except sqlite3.IntegrityError:
                # Skip if this attendance record already exists
                pass
    
    # Commit all changes
    conn.commit()
    print(f"Created {attendance_count} attendance records")

def clear_existing_sessions():
    """Clear all existing sessions from the database"""
    try:
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        confirm = input("⚠️ WARNING: This will delete ALL existing class sessions! Continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            conn.close()
            return False
            
        # Count existing sessions
        cursor.execute("SELECT COUNT(*) FROM class_sessions")
        count = cursor.fetchone()[0]
        
        # Delete all sessions
        cursor.execute("DELETE FROM class_sessions")
        
        # Delete related attendance records
        cursor.execute("DELETE FROM attendance")
        
        conn.commit()
        print(f"Deleted {count} existing sessions and related attendance records")
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error clearing sessions: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def clear_semester_sessions():
    """Clear existing sessions only for the current semester"""
    try:
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get semester date range
        semester_start, semester_end = get_semester_date_range()
        semester_start_str = semester_start.strftime("%Y-%m-%d")
        semester_end_str = semester_end.strftime("%Y-%m-%d")
        
        # Current semester info
        current_semester_num = determine_current_semester()
        
        confirm = input(f"⚠️ WARNING: This will delete existing class sessions for semester {current_semester_num} ({semester_start_str} to {semester_end_str})! Continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            conn.close()
            return False
        
        # Get class IDs for current semester
        cursor.execute("""
            SELECT class_id FROM classes 
            WHERE semester LIKE ?
        """, (f"%.{current_semester_num}",))
        
        semester_classes = [row[0] for row in cursor.fetchall()]
        
        if not semester_classes:
            print("No classes found for the current semester")
            conn.close()
            return False
        
        # Create placeholders for SQL query
        placeholders = ', '.join(['?'] * len(semester_classes))
        
        # Count existing semester sessions
        cursor.execute(f"""
            SELECT COUNT(*) FROM class_sessions 
            WHERE class_id IN ({placeholders})
            AND date BETWEEN ? AND ?
        """, semester_classes + [semester_start_str, semester_end_str])
        
        count = cursor.fetchone()[0]
        
        # Get session IDs to delete
        cursor.execute(f"""
            SELECT session_id FROM class_sessions 
            WHERE class_id IN ({placeholders})
            AND date BETWEEN ? AND ?
        """, semester_classes + [semester_start_str, semester_end_str])
        
        session_ids = [row[0] for row in cursor.fetchall()]
        
        if not session_ids:
            print("No sessions found for the current semester")
            conn.close()
            return False
        
        # Create placeholders for session IDs
        session_placeholders = ', '.join(['?'] * len(session_ids))
        
        # Delete related attendance records
        cursor.execute(f"""
            DELETE FROM attendance 
            WHERE session_id IN ({session_placeholders})
        """, session_ids)
        
        attendance_deleted = cursor.rowcount
        
        # Delete the sessions
        cursor.execute(f"""
            DELETE FROM class_sessions 
            WHERE session_id IN ({session_placeholders})
        """, session_ids)
        
        conn.commit()
        print(f"Deleted {count} sessions and {attendance_deleted} attendance records for the current semester")
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error clearing semester sessions: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("🔵 Class Session Faker")
    print("======================")
    
    # Determine current semester
    current_semester = determine_current_semester()
    print(f"Current semester: {current_semester}")
    
    # Ask how to clear sessions
    clear_option = input("Clear options:\n1. Clear only current semester sessions\n2. Clear all sessions\n3. Don't clear any sessions\nChoose an option (1-3): ")
    
    if clear_option == "1":
        if not clear_semester_sessions():
            sys.exit(1)
    elif clear_option == "2":
        if not clear_existing_sessions():
            sys.exit(1)
    elif clear_option != "3":
        print("Invalid option. Exiting.")
        sys.exit(1)
    
    # Generate new sessions
    generate_class_sessions()