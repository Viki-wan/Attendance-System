#!/usr/bin/env python3
"""
Face Recognition Attendance System - Instructor Data Faker
Generates realistic fake data for instructors, courses, classes, and related tables.
"""

import sqlite3
import random
from faker import Faker
from datetime import datetime, timedelta, date
import bcrypt
import json
from werkzeug.security import generate_password_hash

# Initialize Faker
fake = Faker()

# Configuration
NUM_INSTRUCTORS = 20
NUM_COURSES = 15
NUM_CLASSES = 25

# Sample data for realism
FACULTIES = [
    'Engineering', 'Computer Science', 'Business', 'Mathematics', 
    'Physics', 'Chemistry', 'Biology', 'Literature', 'History', 'Psychology'
]

COURSE_PREFIXES = {
    'Engineering': ['ENG', 'MECH', 'ELEC', 'CIVIL'],
    'Computer Science': ['CS', 'IT', 'SE', 'AI'],
    'Business': ['BUS', 'MGT', 'FIN', 'MKT'],
    'Mathematics': ['MATH', 'STAT', 'CALC'],
    'Physics': ['PHYS', 'ASTRO'],
    'Chemistry': ['CHEM', 'OCHEM'],
    'Biology': ['BIO', 'MICRO', 'GENET'],
    'Literature': ['LIT', 'ENG', 'POET'],
    'History': ['HIST', 'ARCH'],
    'Psychology': ['PSY', 'CLIN', 'DEV']
}

COURSE_TYPES = [
    'Introduction to', 'Advanced', 'Principles of', 'Fundamentals of',
    'Applied', 'Theory and Practice of', 'Modern', 'Contemporary'
]

SEMESTERS = ['1.1', '1.2', '2.1', '2.2', '3.1', '3.2', '4.1', '4.2']

def delete_existing_instructors(cursor):
    cursor.execute('DELETE FROM instructors')
    cursor.execute('DELETE FROM activity_log WHERE user_type = "instructor"')
    cursor.execute('DELETE FROM lecturer_preferences')
    cursor.execute('DELETE FROM instructor_courses')
    cursor.execute('DELETE FROM class_instructors')
    # Add more deletes as needed for related tables
    print('🗑️  Deleted existing instructor-related data.')

def hash_password(password):
    """Hash a password using werkzeug.security.generate_password_hash."""
    return generate_password_hash(password)

def generate_course_code(faculty, existing_codes):
    """Generate a unique course code."""
    prefixes = COURSE_PREFIXES.get(faculty, ['GEN'])
    while True:
        prefix = random.choice(prefixes)
        number = random.randint(100, 499)
        code = f"{prefix}{number}"
        if code not in existing_codes:
            existing_codes.add(code)
            return code

def generate_class_id(course_code, year, semester, existing_ids):
    """Generate a unique class ID."""
    base_id = f"{course_code}-Y{year}S{semester.replace('.', '')}"
    counter = 1
    class_id = base_id
    while class_id in existing_ids:
        class_id = f"{base_id}-{counter}"
        counter += 1
    existing_ids.add(class_id)
    return class_id

def generate_lecturer_id(year, seq_num):
    return f"L{year}{seq_num:03d}"

def create_fake_data(db_path='attendance.db'):
    """Generate and insert fake data into the database."""
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("🚀 Starting data generation...")
        delete_existing_instructors(cursor)
        
        # Generate Admin
        print("📋 Creating admin user...")
        admin_data = {
            'username': 'admin',
            'password': hash_password('admin123')
        }
        cursor.execute('''
            INSERT OR REPLACE INTO admin (username, password) 
            VALUES (?, ?)
        ''', (admin_data['username'], admin_data['password']))
        
        # Generate Instructors
        print(f"👨‍🏫 Generating {NUM_INSTRUCTORS} instructors...")
        instructors = []
        instructor_phones = set()
        instructor_emails = set()
        instructor_ids = []
        
        for i in range(NUM_INSTRUCTORS):
            lecturer_id = generate_lecturer_id(datetime.now().year, i+1)
            while True:
                phone = fake.phone_number()[:15]  # Limit length
                email = fake.email()
                if phone not in instructor_phones and email not in instructor_emails:
                    instructor_phones.add(phone)
                    instructor_emails.add(email)
                    break
            
            instructor = {
                'instructor_id': lecturer_id,
                'instructor_name': fake.name(),
                'email': email,
                'phone': phone,
                'password': hash_password('instructor123'),
                'faculty': random.choice(FACULTIES),
                'created_at': fake.date_time_between(start_date='-2y', end_date='now'),
                'last_login': None,  # For first-time setup
                'is_active': 1 if random.random() > 0.1 else 0
            }
            instructors.append(instructor)
            instructor_ids.append(lecturer_id)
            
            cursor.execute('''
                INSERT INTO instructors 
                (instructor_id, instructor_name, email, phone, password, faculty, created_at, last_login, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                instructor['instructor_id'], instructor['instructor_name'], instructor['email'], instructor['phone'],
                instructor['password'], instructor['faculty'], instructor['created_at'],
                instructor['last_login'], instructor['is_active']
            ))
        
        # Get instructor IDs
        cursor.execute("SELECT instructor_id, faculty FROM instructors")
        instructor_data = cursor.fetchall()
        
        # Generate Courses
        print(f"📚 Generating {NUM_COURSES} courses...")
        courses = []
        existing_course_codes = set()
        
        for i in range(NUM_COURSES):
            faculty = random.choice(FACULTIES)
            course_code = generate_course_code(faculty, existing_course_codes)
            course_type = random.choice(COURSE_TYPES)
            subject_area = faculty.split()[0] if len(faculty.split()) > 1 else faculty
            
            course = {
                'course_code': course_code,
                'course_name': f"{course_type} {subject_area}",
                'faculty': faculty,
                'created_at': fake.date_time_between(start_date='-3y', end_date='-1y'),
                'is_active': 1 if random.random() > 0.05 else 0
            }
            courses.append(course)
            
            cursor.execute('''
                INSERT INTO courses (course_code, course_name, faculty, created_at, is_active)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                course['course_code'], course['course_name'], course['faculty'],
                course['created_at'], course['is_active']
            ))
        
        # Generate Classes
        print(f"🏫 Generating {NUM_CLASSES} classes...")
        classes = []
        existing_class_ids = set()
        
        for i in range(NUM_CLASSES):
            course = random.choice(courses)
            year = random.randint(1, 4)
            semester = random.choice(SEMESTERS)
            class_id = generate_class_id(course['course_code'], year, semester, existing_class_ids)
            
            class_data = {
                'class_id': class_id,
                'course_code': course['course_code'],
                'class_name': f"{course['course_name']} - Year {year} Semester {semester}",
                'year': year,
                'semester': semester,
                'created_at': fake.date_time_between(start_date='-1y', end_date='now'),
                'is_active': 1 if random.random() > 0.1 else 0
            }
            classes.append(class_data)
            
            cursor.execute('''
                INSERT INTO classes (class_id, course_code, class_name, year, semester, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                class_data['class_id'], class_data['course_code'], class_data['class_name'],
                class_data['year'], class_data['semester'], class_data['created_at'],
                class_data['is_active']
            ))
        
        # Generate Instructor-Course relationships
        print("🔗 Creating instructor-course relationships...")
        for instructor_id, instructor_faculty in instructor_data:
            # Each instructor teaches 1-4 courses, preferably in their faculty
            num_courses = random.randint(1, 4)
            
            # Get courses preferably from same faculty
            same_faculty_courses = [c for c in courses if c['faculty'] == instructor_faculty]
            other_courses = [c for c in courses if c['faculty'] != instructor_faculty]
            
            available_courses = same_faculty_courses + other_courses
            selected_courses = random.sample(
                available_courses, 
                min(num_courses, len(available_courses))
            )
            
            for course in selected_courses:
                semester = random.choice(SEMESTERS)
                year = random.randint(2023, 2024)
                is_coordinator = 1 if random.random() < 0.2 else 0
                
                cursor.execute('''
                    INSERT OR IGNORE INTO instructor_courses 
                    (instructor_id, course_code, semester, year, is_coordinator)
                    VALUES (?, ?, ?, ?, ?)
                ''', (instructor_id, course['course_code'], semester, year, is_coordinator))
        
        # Generate Class-Instructor relationships
        print("👨‍🏫 Assigning instructors to classes...")
        for class_data in classes:
            # Find instructors who teach this course
            cursor.execute('''
                SELECT DISTINCT ic.instructor_id 
                FROM instructor_courses ic 
                WHERE ic.course_code = ?
            ''', (class_data['course_code'],))
            
            available_instructors = cursor.fetchall()
            if available_instructors:
                # Assign 1-2 instructors per class
                num_instructors = random.randint(1, min(2, len(available_instructors)))
                selected_instructors = random.sample(available_instructors, num_instructors)
                
                for instructor_tuple in selected_instructors:
                    instructor_id = instructor_tuple[0]
                    assigned_date = fake.date_between(start_date='-6m', end_date='now')
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO class_instructors 
                        (class_id, instructor_id, assigned_date)
                        VALUES (?, ?, ?)
                    ''', (class_data['class_id'], instructor_id, assigned_date))
        
        # Generate Lecturer Preferences
        print("⚙️ Creating lecturer preferences...")
        themes = ['light', 'dark', 'auto']
        layouts = ['default', 'compact', 'detailed']
        timezones = ['UTC', 'Africa/Nairobi', 'America/New_York', 'Europe/London']
        languages = ['en', 'sw', 'fr']
        
        for instructor_id, _ in instructor_data:
            preferences = {
                'instructor_id': instructor_id,
                'theme': random.choice(themes),
                'dashboard_layout': random.choice(layouts),
                'notification_settings': json.dumps({
                    'email_notifications': random.choice([True, False]),
                    'push_notifications': random.choice([True, False]),
                    'attendance_alerts': random.choice([True, False])
                }),
                'auto_refresh_interval': random.choice([15, 30, 60, 120]),
                'default_session_duration': random.choice([60, 90, 120, 150]),
                'timezone': random.choice(timezones),
                'language': random.choice(languages),
                'created_at': fake.date_time_between(start_date='-1y', end_date='now')
            }
            
            cursor.execute('''
                INSERT INTO lecturer_preferences 
                (instructor_id, theme, dashboard_layout, notification_settings,
                 auto_refresh_interval, default_session_duration, timezone, language, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                preferences['instructor_id'], preferences['theme'], preferences['dashboard_layout'],
                preferences['notification_settings'], preferences['auto_refresh_interval'],
                preferences['default_session_duration'], preferences['timezone'],
                preferences['language'], preferences['created_at']
            ))
        
        # Generate some Class Sessions
        print("📅 Creating sample class sessions...")
        session_statuses = ['scheduled', 'ongoing', 'completed', 'cancelled', 'dismissed']
        
        for i in range(50):  # Generate 50 sample sessions
            class_data = random.choice(classes)
            
            # Get an instructor for this class
            cursor.execute('''
                SELECT instructor_id FROM class_instructors WHERE class_id = ? LIMIT 1
            ''', (class_data['class_id'],))
            instructor_result = cursor.fetchone()
            
            if instructor_result:
                instructor_id = instructor_result[0]
                session_date = fake.date_between(start_date='-30d', end_date='+7d')
                start_time = fake.time()
                
                # Calculate end time (1-3 hours later)
                start_datetime = datetime.combine(session_date, datetime.strptime(start_time, '%H:%M:%S').time())
                end_datetime = start_datetime + timedelta(hours=random.randint(1, 3))
                end_time = end_datetime.strftime('%H:%M:%S')
                
                status = random.choice(session_statuses)
                attendance_count = random.randint(0, 50) if status == 'completed' else 0
                total_students = random.randint(attendance_count, 60)
                
                cursor.execute('''
                    INSERT INTO class_sessions 
                    (class_id, date, start_time, end_time, status, created_by, 
                     attendance_count, total_students, session_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    class_data['class_id'], session_date.strftime('%Y-%m-%d'),
                    start_time, end_time, status, instructor_id,
                    attendance_count, total_students,
                    fake.text(max_nb_chars=200) if random.choice([True, False]) else None
                ))
        
        # Generate Activity Log entries
        print("📊 Creating activity log entries...")
        activity_types = [
            'login', 'logout', 'create_session', 'start_session', 'end_session',
            'mark_attendance', 'dismiss_session', 'update_profile', 'view_report'
        ]
        
        for i in range(200):  # Generate 200 activity log entries
            instructor_id, _ = random.choice(instructor_data)
            activity_type = random.choice(activity_types)
            
            descriptions = {
                'login': 'User logged into the system',
                'logout': 'User logged out of the system',
                'create_session': 'Created a new class session',
                'start_session': 'Started a class session',
                'end_session': 'Ended a class session',
                'mark_attendance': 'Marked student attendance',
                'dismiss_session': 'Dismissed a class session',
                'update_profile': 'Updated profile information',
                'view_report': 'Viewed attendance report'
            }
            
            cursor.execute('''
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                str(instructor_id), 'instructor', activity_type,
                descriptions.get(activity_type, f"Performed {activity_type}"),
                fake.date_time_between(start_date='-30d', end_date='now')
            ))
        
        # Generate Notifications
        print("🔔 Creating notifications...")
        notification_types = ['info', 'warning', 'success', 'error']
        priorities = ['low', 'normal', 'high', 'urgent']
        
        for i in range(100):  # Generate 100 notifications
            instructor_id, _ = random.choice(instructor_data)
            notification_type = random.choice(notification_types)
            priority = random.choice(priorities)
            
            titles_by_type = {
                'info': ['Session Reminder', 'New Student Enrolled', 'System Update'],
                'warning': ['Low Attendance Alert', 'Session Overdue', 'Profile Incomplete'],
                'success': ['Session Completed', 'Report Generated', 'Profile Updated'],
                'error': ['Session Failed', 'Camera Error', 'Connection Lost']
            }
            
            title = random.choice(titles_by_type.get(notification_type, ['Notification']))
            message = fake.text(max_nb_chars=150)
            
            created_at = fake.date_time_between(start_date='-7d', end_date='now')
            expires_at = created_at + timedelta(days=random.randint(1, 30))
            
            cursor.execute('''
                INSERT INTO notifications 
                (user_id, user_type, title, message, type, is_read, created_at, expires_at, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(instructor_id), 'instructor', title, message, notification_type,
                random.choice([0, 1]), created_at, expires_at, priority
            ))
        
        # Commit all changes
        conn.commit()
        print("✅ Data generation completed successfully!")
        
        # Print summary
        cursor.execute("SELECT COUNT(*) FROM instructors")
        instructor_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM courses")
        course_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM classes")
        class_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM class_sessions")
        session_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM activity_log WHERE user_type = 'instructor'")
        activity_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_type = 'instructor'")
        notification_count = cursor.fetchone()[0]
        
        print(f"""
📈 Summary:
   • Instructors: {instructor_count}
   • Courses: {course_count}
   • Classes: {class_count}
   • Class Sessions: {session_count}
   • Activity Log Entries: {activity_count}
   • Notifications: {notification_count}
   • Admin User: 1 (username: admin, password: admin123)
   
🔑 Default Credentials:
   • Admin: username=admin, password=admin123
   • Instructors: password=instructor123 (for all)
   
💾 Database: {db_path}
        """)
        
        print("\n🔑 Instructor Credentials:")
        for instructor in instructors:
            print(f"   • ID: {instructor['instructor_id']} | Name: {instructor['instructor_name']} | Password: instructor123")
        
    except Exception as e:
        print(f"❌ Error generating data: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("🎭 Face Recognition Attendance System - Instructor Data Faker")
    print("=" * 60)
    
    # You can specify a different database path here
    db_path = input("Enter database path (or press Enter for 'attendance.db'): ").strip()
    if not db_path:
        db_path = 'attendance.db'
    
    try:
        create_fake_data(db_path)
    except KeyboardInterrupt:
        print("\n⚠️ Data generation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Failed to generate data: {e}")
