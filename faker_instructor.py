#!/usr/bin/env python3
"""
Face Recognition Attendance System - Instructor Data Faker
Generates realistic fake instructors and assigns them to existing courses, classes, and sessions.
Supports department-based assignments with shared class capabilities.
"""

import sqlite3
import random
from faker import Faker
from datetime import datetime, date
import hashlib
import re

# Initialize Faker
fake = Faker()

# Database configuration
DATABASE_PATH = "attendance.db"

# Configuration
NUM_INSTRUCTORS = 25  # Generate at least 20 lecturers (increased to 25)
INSTRUCTORS_PER_DEPARTMENT = 4  # Reduced per department since we have 6 departments
SHARED_CLASS_PROBABILITY = 0.3  # Probability of instructor having shared classes
MAX_CLASSES_PER_INSTRUCTOR = 8  # Maximum classes per instructor
MAX_SESSIONS_PER_INSTRUCTOR = 20  # Maximum sessions per instructor

# Department mapping from course codes
DEPARTMENT_MAPPING = {
    "S13": "Computer Science",
    "S11": "General Sciences", 
    "S18": "Statistics",
    "S19": "Actuarial Science",
    "S14": "Applied Computer Science",
    "S20": "Mathematics"
}

# Academic titles and specializations
ACADEMIC_TITLES = [
    "Dr.", "Prof.", "Mr.", "Ms.", "Mrs."
]

SPECIALIZATIONS = {
    "Computer Science": [
        "Software Engineering", "Artificial Intelligence", "Data Structures", 
        "Computer Networks", "Database Systems", "Web Development",
        "Machine Learning", "Cybersecurity", "Mobile Development"
    ],
    "General Sciences": [
        "Physics", "Chemistry", "Biology", "Environmental Science",
        "Laboratory Methods", "Scientific Computing", "Research Methods"
    ],
    "Statistics": [
        "Statistical Analysis", "Probability Theory", "Data Analysis",
        "Statistical Computing", "Survey Methods", "Quality Control"
    ],
    "Actuarial Science": [
        "Risk Management", "Financial Mathematics", "Insurance Mathematics",
        "Life Contingencies", "Pension Mathematics", "Actuarial Modeling"
    ],
    "Applied Computer Science": [
        "Applied Programming", "Business Applications", "System Analysis",
        "Project Management", "IT Infrastructure", "Enterprise Systems"
    ],
    "Mathematics": [
        "Calculus", "Linear Algebra", "Discrete Mathematics", "Real Analysis",
        "Differential Equations", "Mathematical Modeling", "Numerical Analysis"
    ]
}

def create_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def hash_password(password):
    """Hash a password using werkzeug.security.generate_password_hash to match lecturer panel."""
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)
    except ImportError:
        # Fallback to SHA-256 if werkzeug not available
        return hashlib.sha256(password.encode()).hexdigest()

def get_existing_courses():
    """Get all existing courses from the database."""
    conn = create_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT course_code, course_name, faculty FROM courses WHERE is_active = 1")
        courses = cursor.fetchall()
        return courses
    except sqlite3.Error as e:
        print(f"Error getting courses: {e}")
        return []
    finally:
        conn.close()

def get_existing_classes():
    """Get all existing classes from the database."""
    conn = create_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT class_id, course_code, class_name, year, semester 
            FROM classes 
            WHERE is_active = 1
            ORDER BY course_code, year, semester
        """)
        classes = cursor.fetchall()
        return classes
    except sqlite3.Error as e:
        print(f"Error getting classes: {e}")
        return []
    finally:
        conn.close()

def get_existing_sessions():
    """Get all existing sessions from the database."""
    conn = create_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, class_id, date, start_time, end_time, status
            FROM class_sessions
            ORDER BY date, start_time
        """)
        sessions = cursor.fetchall()
        return sessions
    except sqlite3.Error as e:
        print(f"Error getting sessions: {e}")
        return []
    finally:
        conn.close()

def generate_instructor_id(sequence):
    """Generate a unique instructor ID in format L2025001, L2025002, etc."""
    current_year = datetime.now().year
    return f"L{current_year}{sequence:03d}"

def generate_instructor_name():
    """Generate a realistic instructor name."""
    title = random.choice(ACADEMIC_TITLES)
    first_name = fake.first_name()
    last_name = fake.last_name()
    return f"{title} {first_name} {last_name}"

def generate_instructor_email(name, department):
    """Generate a realistic email address."""
    # Clean the name for email
    clean_name = re.sub(r'[^a-zA-Z\s]', '', name.lower())
    parts = clean_name.split()
    
    if len(parts) >= 3:  # Dr. John Smith -> john.smith
        first = parts[1]
        last = parts[2]
    elif len(parts) == 2:  # John Smith -> john.smith
        first = parts[0]
        last = parts[1]
    else:  # Fallback
        first = parts[0]
        last = "instructor"
    
    # Add department suffix
    dept_suffix = department.lower().replace(" ", "")
    return f"{first}.{last}@{dept_suffix}.university.edu"

def generate_phone_number():
    """Generate a realistic phone number."""
    return f"07{random.randint(10000000, 99999999)}"

def get_department_from_course(course_code):
    """Get department name from course code."""
    return DEPARTMENT_MAPPING.get(course_code, "General Studies")

def clear_existing_instructors(conn):
    """Clear existing instructor data for clean insertion."""
    try:
        cursor = conn.cursor()
        
        # Delete in order to respect foreign key constraints
        # Check if lecturer_preferences table exists before trying to delete
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lecturer_preferences'")
        if cursor.fetchone():
            cursor.execute("DELETE FROM lecturer_preferences")
        
        cursor.execute("DELETE FROM class_instructors")
        cursor.execute("DELETE FROM instructor_courses")
        cursor.execute("DELETE FROM activity_log WHERE user_type = 'instructor'")
        cursor.execute("DELETE FROM instructors")
        
        print("🗑️  Cleared existing instructor data")
        return True
    except sqlite3.Error as e:
        print(f"Error clearing instructor data: {e}")
        return False

def insert_instructor(conn, instructor_data):
    """Insert a single instructor into the database."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO instructors 
            (instructor_id, instructor_name, email, phone, password, faculty, 
             created_at, last_login, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            instructor_data['instructor_id'],
            instructor_data['instructor_name'],
            instructor_data['email'],
            instructor_data['phone'],
            instructor_data['password'],
            instructor_data['faculty'],
            instructor_data['created_at'],
            instructor_data['last_login'],
            instructor_data['is_active']
        ))
        
        return True
    except sqlite3.Error as e:
        print(f"Error inserting instructor {instructor_data['instructor_id']}: {e}")
        return False

def assign_instructor_to_course(conn, instructor_id, course_code, semester=None, year=None, is_coordinator=False):
    """Assign an instructor to a course."""
    try:
        cursor = conn.cursor()
        
        # Use current semester/year if not specified
        if not semester:
            semester = f"{datetime.now().year}.1"  # Default to first semester
        if not year:
            year = datetime.now().year
        
        cursor.execute("""
            INSERT INTO instructor_courses 
            (instructor_id, course_code, semester, year, is_coordinator)
            VALUES (?, ?, ?, ?, ?)
        """, (instructor_id, course_code, semester, year, is_coordinator))
        
        return True
    except sqlite3.Error as e:
        print(f"Error assigning instructor {instructor_id} to course {course_code}: {e}")
        return False

def assign_instructor_to_class(conn, instructor_id, class_id):
    """Assign an instructor to a class."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO class_instructors 
            (class_id, instructor_id, assigned_date)
            VALUES (?, ?, ?)
        """, (class_id, instructor_id, date.today()))
        
        return True
    except sqlite3.Error as e:
        print(f"Error assigning instructor {instructor_id} to class {class_id}: {e}")
        return False

def check_session_conflict(session1, session2):
    """Check if two sessions conflict (same date and overlapping times)."""
    session_id1, date1, start1, end1, status1 = session1
    session_id2, date2, start2, end2, status2 = session2
    
    # Different dates = no conflict
    if date1 != date2:
        return False
    
    # Same date - check time overlap
    # Convert time strings to comparable format
    def time_to_minutes(time_str):
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    
    start1_min = time_to_minutes(start1)
    end1_min = time_to_minutes(end1)
    start2_min = time_to_minutes(start2)
    end2_min = time_to_minutes(end2)
    
    # Check for overlap: sessions conflict if one starts before the other ends
    return not (end1_min <= start2_min or end2_min <= start1_min)

def get_non_conflicting_sessions(instructor_sessions, max_sessions):
    """Get a set of non-conflicting sessions for an instructor."""
    if len(instructor_sessions) <= max_sessions:
        # Check all sessions for conflicts
        non_conflicting = []
        for session in instructor_sessions:
            has_conflict = False
            for existing_session in non_conflicting:
                if check_session_conflict(session, existing_session):
                    has_conflict = True
                    break
            if not has_conflict:
                non_conflicting.append(session)
        return non_conflicting
    
    # If we have more sessions than max, try to find the best non-conflicting set
    non_conflicting = []
    remaining_sessions = instructor_sessions.copy()
    
    # Sort by date and start time for better selection
    remaining_sessions.sort(key=lambda x: (x[1], x[2]))  # Sort by date, then start time
    
    for session in remaining_sessions:
        if len(non_conflicting) >= max_sessions:
            break
            
        has_conflict = False
        for existing_session in non_conflicting:
            if check_session_conflict(session, existing_session):
                has_conflict = True
                break
        
        if not has_conflict:
            non_conflicting.append(session)
    
    return non_conflicting

def assign_instructor_to_session(conn, instructor_id, session_id):
    """Assign an instructor to a session (update created_by field) if not already assigned."""
    try:
        cursor = conn.cursor()
        
        # Check if session is already assigned to another instructor
        cursor.execute("SELECT created_by FROM class_sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()
        
        if result and result[0] is not None:
            # Session already assigned to another instructor
            return False
        
        cursor.execute("""
            UPDATE class_sessions 
            SET created_by = ?
            WHERE session_id = ?
        """, (instructor_id, session_id))
        
        return True
    except sqlite3.Error as e:
        print(f"Error assigning instructor {instructor_id} to session {session_id}: {e}")
        return False

def create_lecturer_preferences(conn, instructor_id):
    """Create default lecturer preferences if table exists."""
    try:
        cursor = conn.cursor()
        
        # Check if lecturer_preferences table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lecturer_preferences'")
        if not cursor.fetchone():
            print(f"   ⚠️  lecturer_preferences table not found, skipping preferences for {instructor_id}")
            return True
        
        preferences = {
            "theme": random.choice(["light", "dark"]),
            "dashboard_layout": random.choice(["default", "compact", "detailed"]),
            "auto_refresh_interval": random.randint(30, 120),
            "default_session_duration": random.choice([60, 90, 120]),
            "timezone": "UTC",
            "language": "en"
        }
        
        cursor.execute("""
            INSERT INTO lecturer_preferences 
            (instructor_id, theme, dashboard_layout, notification_settings, 
             auto_refresh_interval, default_session_duration, timezone, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            instructor_id,
            preferences["theme"],
            preferences["dashboard_layout"],
            "{}",  # Empty JSON for notification settings
            preferences["auto_refresh_interval"],
            preferences["default_session_duration"],
            preferences["timezone"],
            preferences["language"]
        ))
        
        return True
    except sqlite3.Error as e:
        print(f"Error creating preferences for instructor {instructor_id}: {e}")
        return False

def generate_instructors():
    """Generate instructors and assign them to courses, classes, and sessions."""
    conn = create_connection()
    if conn is None:
        return
    
    try:
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Get existing data
        courses = get_existing_courses()
        classes = get_existing_classes()
        sessions = get_existing_sessions()
        
        if not courses:
            print("❌ No courses found. Please run course faker first.")
            return
        
        print(f"📚 Found {len(courses)} courses")
        print(f"🏫 Found {len(classes)} classes")
        print(f"📅 Found {len(sessions)} sessions")
        
        # Clear existing instructor data
        if not clear_existing_instructors(conn):
            return
        
        # Group courses by department
        courses_by_department = {}
        for course_code, course_name, faculty in courses:
            department = get_department_from_course(course_code)
            if department not in courses_by_department:
                courses_by_department[department] = []
            courses_by_department[department].append((course_code, course_name, faculty))
        
        print(f"🏢 Departments found: {list(courses_by_department.keys())}")
        
        # Generate instructors by department
        generated_instructors = []
        instructor_sequence = 1
        
        # Calculate total instructors needed and distribute across departments
        total_departments = len(courses_by_department)
        instructors_per_dept = max(INSTRUCTORS_PER_DEPARTMENT, NUM_INSTRUCTORS // total_departments)
        
        for department, dept_courses in courses_by_department.items():
            print(f"\n👨‍🏫 Generating instructors for {department}...")
            
            # Ensure we generate enough instructors to meet minimum requirement
            num_instructors = instructors_per_dept
            
            for _ in range(num_instructors):
                # Generate instructor data
                instructor_id = generate_instructor_id(instructor_sequence)
                instructor_name = generate_instructor_name()
                email = generate_instructor_email(instructor_name, department)
                phone = generate_phone_number()
                
                # Ensure unique email and phone
                while True:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM instructors WHERE email = ? OR phone = ?", 
                                 (email, phone))
                    if cursor.fetchone()[0] == 0:
                        break
                    email = generate_instructor_email(instructor_name, department)
                    phone = generate_phone_number()
                
                instructor_data = {
                    'instructor_id': instructor_id,
                    'instructor_name': instructor_name,
                    'email': email,
                    'phone': phone,
                    'password': hash_password("instructor123"),
                    'faculty': department,
                    'created_at': fake.date_time_between(start_date='-2y', end_date='now'),
                    'last_login': None,
                    'is_active': 1 if random.random() > 0.05 else 0  # 95% active
                }
                
                # Insert instructor
                if insert_instructor(conn, instructor_data):
                    generated_instructors.append(instructor_data)
                    
                    # Create lecturer preferences
                    create_lecturer_preferences(conn, instructor_id)
                    
                    # Assign to primary course (department-based)
                    primary_course = random.choice(dept_courses)[0]
                    assign_instructor_to_course(conn, instructor_id, primary_course, 
                                              is_coordinator=random.random() < 0.2)  # 20% coordinators
                    
                    # Assign to additional courses (shared classes)
                    if random.random() < SHARED_CLASS_PROBABILITY:
                        additional_courses = random.sample(
                            [c[0] for c in courses if c[0] != primary_course], 
                            min(random.randint(1, 2), len(courses) - 1)
                        )
                        for course_code in additional_courses:
                            assign_instructor_to_course(conn, instructor_id, course_code)
                    
                    instructor_sequence += 1
                    print(f"   ✅ Created {instructor_name} ({instructor_id})")
        
        print(f"\n👥 Generated {len(generated_instructors)} instructors")
        
        # Assign instructors to classes
        print("\n🏫 Assigning instructors to classes...")
        classes_by_course = {}
        for class_id, course_code, class_name, year, semester in classes:
            if course_code not in classes_by_course:
                classes_by_course[course_code] = []
            classes_by_course[course_code].append((class_id, class_name, year, semester))
        
        assigned_classes = 0
        for instructor in generated_instructors:
            if not instructor['is_active']:
                continue
                
            # Get instructor's courses
            cursor = conn.cursor()
            cursor.execute("SELECT course_code FROM instructor_courses WHERE instructor_id = ?", 
                         (instructor['instructor_id'],))
            instructor_courses = [row[0] for row in cursor.fetchall()]
            
            # Assign classes from instructor's courses
            instructor_classes = []
            for course_code in instructor_courses:
                if course_code in classes_by_course:
                    course_classes = classes_by_course[course_code]
                    # Assign 1-3 classes per course
                    num_classes = min(random.randint(1, 3), len(course_classes))
                    selected_classes = random.sample(course_classes, num_classes)
                    instructor_classes.extend(selected_classes)
            
            # Limit total classes per instructor
            if len(instructor_classes) > MAX_CLASSES_PER_INSTRUCTOR:
                instructor_classes = random.sample(instructor_classes, MAX_CLASSES_PER_INSTRUCTOR)
            
            # Assign classes
            for class_id, class_name, year, semester in instructor_classes:
                if assign_instructor_to_class(conn, instructor['instructor_id'], class_id):
                    assigned_classes += 1
        
        print(f"   ✅ Assigned {assigned_classes} class-instructor relationships")
        
        # Assign instructors to sessions
        print("\n📅 Assigning instructors to sessions...")
        sessions_by_class = {}
        for session_id, class_id, session_date, start_time, end_time, status in sessions:
            if class_id not in sessions_by_class:
                sessions_by_class[class_id] = []
            sessions_by_class[class_id].append((session_id, session_date, start_time, end_time, status))
        
        assigned_sessions = 0
        for instructor in generated_instructors:
            if not instructor['is_active']:
                continue
            
            # Get instructor's classes
            cursor = conn.cursor()
            cursor.execute("SELECT class_id FROM class_instructors WHERE instructor_id = ?", 
                         (instructor['instructor_id'],))
            instructor_classes = [row[0] for row in cursor.fetchall()]
            
            # Get sessions already assigned to this instructor
            cursor.execute("""
                SELECT cs.session_id, cs.date, cs.start_time, cs.end_time, cs.status
                FROM class_sessions cs
                WHERE cs.created_by = ?
            """, (instructor['instructor_id'],))
            already_assigned_sessions = cursor.fetchall()
            
            # Assign sessions from instructor's classes
            instructor_sessions = []
            for class_id in instructor_classes:
                if class_id in sessions_by_class:
                    class_sessions = sessions_by_class[class_id]
                    # Assign 1-5 sessions per class
                    num_sessions = min(random.randint(1, 5), len(class_sessions))
                    selected_sessions = random.sample(class_sessions, num_sessions)
                    instructor_sessions.extend(selected_sessions)
            
            # Combine with already assigned sessions for conflict checking
            all_sessions = already_assigned_sessions + instructor_sessions
            
            # Get non-conflicting sessions (excluding already assigned ones)
            non_conflicting_sessions = get_non_conflicting_sessions(all_sessions, MAX_SESSIONS_PER_INSTRUCTOR)
            
            # Filter out sessions that are already assigned
            new_sessions = [s for s in non_conflicting_sessions if s not in already_assigned_sessions]
            
            # Assign new sessions
            for session_id, session_date, start_time, end_time, status in new_sessions:
                if assign_instructor_to_session(conn, instructor['instructor_id'], session_id):
                    assigned_sessions += 1
            
            # Log conflicts if any
            conflicts = len(instructor_sessions) - len(new_sessions)
            if conflicts > 0:
                print(f"   ⚠️  Skipped {conflicts} conflicting sessions for {instructor['instructor_name']}")
        
        print(f"   ✅ Assigned {assigned_sessions} session-instructor relationships")
        
        # Commit transaction
        conn.commit()
        print(f"\n🎉 Successfully generated {len(generated_instructors)} instructors!")
        print(f"   📊 Classes assigned: {assigned_classes}")
        print(f"   📊 Sessions assigned: {assigned_sessions}")
        
    except Exception as e:
        # Rollback in case of error
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def main():
    """Main function to run the instructor faker."""
    print("👨‍🏫 Instructor Data Faker")
    print("=" * 30)
    
    # Check if database exists and has required data
    conn = create_connection()
    if conn is None:
        print("❌ Cannot connect to database")
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if courses exist
        cursor.execute("SELECT COUNT(*) FROM courses WHERE is_active = 1")
        course_count = cursor.fetchone()[0]
        
        if course_count == 0:
            print("❌ No active courses found. Please run course faker first.")
            return
        
        # Check if classes exist
        cursor.execute("SELECT COUNT(*) FROM classes WHERE is_active = 1")
        class_count = cursor.fetchone()[0]
        
        if class_count == 0:
            print("❌ No active classes found. Please run class faker first.")
            return
        
        print(f"✅ Found {course_count} courses and {class_count} classes")
        
    finally:
        conn.close()
    
    # Generate instructors
    generate_instructors()

if __name__ == "__main__":
    main()
