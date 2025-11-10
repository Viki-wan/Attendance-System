"""
Faker Script 1: Courses and Instructors
Generates courses and instructors with proper relationships
Run this FIRST before other faker scripts
"""

import sys
import os
from datetime import datetime
import random

# Get the absolute path to the project root (attendance system folder)
current_dir = os.path.dirname(os.path.abspath(__file__))  # faker folder
project_root = os.path.dirname(current_dir)  # attendance system folder
lec_panel_dir = os.path.join(project_root, 'lec_panel')  # lec_panel folder

# Add lec_panel to path so we can import from it
sys.path.insert(0, lec_panel_dir)

# Also add faker directory for faker_config
sys.path.insert(0, current_dir)

print(f"Current Directory: {current_dir}")
print(f"Project Root: {project_root}")
print(f"Lec Panel Directory: {lec_panel_dir}")
print(f"Python Path: {sys.path[:3]}")

# Now import from lec_panel
from app import create_app, db
from app.models.course import Course, InstructorCourse
from app.models.user import Instructor

# Import faker_config
from faker_config import (
    COURSES, FACULTY, INSTRUCTOR_NAMES, CURRENT_YEAR, 
    CURRENT_SEMESTER, generate_instructor_id, get_email, generate_phone,
    HOLIDAYS
)

def clear_existing_data():
    """Clear existing courses and instructors"""
    print("\n🗑️  Clearing existing data...")
    
    try:
        # Delete in correct order (junction tables first)
        InstructorCourse.query.delete()
        Instructor.query.delete()
        Course.query.delete()
        
        db.session.commit()
        print("✅ Existing data cleared")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing data: {e}")
        raise

def generate_courses():
    """Generate all 6 courses"""
    print("\n📚 Generating Courses...")
    
    courses = []
    for course_code, info in COURSES.items():
        course = Course(
            course_code=course_code,
            course_name=info["name"],
            faculty=FACULTY,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        courses.append(course)
        db.session.add(course)
        print(f"  ✓ {course_code}: {info['name']}")
    
    db.session.commit()
    print(f"✅ {len(courses)} courses created")
    return courses

def generate_instructors():
    """Generate instructors"""
    print("\n👨‍🏫 Generating Instructors...")
    
    instructors = []
    
    for idx, name in enumerate(INSTRUCTOR_NAMES, start=1):
        instructor_id = generate_instructor_id(idx)
        email = get_email(name, "staff.university.ac.ke")
        phone = generate_phone()
        
        instructor = Instructor(
            instructor_id=instructor_id,
            instructor_name=name,
            email=email,
            phone=phone,
            faculty=FACULTY,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login=None  # First time login required
        )
        
        # Set default password (instructor_id)
        instructor.set_password(instructor_id)
        
        instructors.append(instructor)
        db.session.add(instructor)
        
        print(f"  ✓ {instructor_id}: {name} | {email} | {phone}")
    
    db.session.commit()
    print(f"✅ {len(instructors)} instructors created")
    return instructors

def assign_instructors_to_courses(instructors, courses):
    """Assign instructors to courses"""
    print("\n🔗 Assigning Instructors to Courses...")
    
    assignments = []
    
    # Ensure each course has at least 2-3 instructors
    for course in courses:
        # Select 2-4 random instructors for each course
        num_instructors = random.randint(2, 4)
        selected_instructors = random.sample(instructors, num_instructors)
        
        # First instructor is coordinator
        for idx, instructor in enumerate(selected_instructors):
            assignment = InstructorCourse(
                instructor_id=instructor.instructor_id,
                course_code=course.course_code,
                semester=CURRENT_SEMESTER,
                year=CURRENT_YEAR,
                is_coordinator=(idx == 0)  # First one is coordinator
            )
            assignments.append(assignment)
            db.session.add(assignment)
            
            role = "Coordinator" if idx == 0 else "Instructor"
            print(f"  ✓ {instructor.instructor_name} → {course.course_code} ({role})")
    
    db.session.commit()
    print(f"✅ {len(assignments)} instructor-course assignments created")
    return assignments

def create_admin_account():
    """Create admin account"""
    print("\n🔐 Creating Admin Account...")
    
    from app.models.user import Admin
    
    # Check if admin exists
    if Admin.query.filter_by(email='admin@university.ac.ke').first():
        print("  ℹ️  Admin already exists")
        return
    
    admin = Admin(
        admin_id='ADMIN001',
        admin_name='System Administrator',
        email='admin@university.ac.ke',
        phone='+254700000000',
        is_active=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    admin.set_password('admin123')  # Change this in production!
    
    db.session.add(admin)
    db.session.commit()
    
    print(f"  ✓ Admin: {admin.admin_name} | {admin.email}")
    print("  ⚠️  Password: admin123 (CHANGE THIS!)")

def insert_default_settings():
    """Insert default system settings"""
    print("\n⚙️  Inserting Default Settings...")
    
    from app.models.settings import Settings
    
    # Check if settings exist
    if Settings.query.count() > 0:
        print("  ℹ️  Settings already exist")
        return
    
    default_settings = [
        ('face_recognition_threshold', '0.6', 'Threshold for face recognition accuracy', 'face_recognition'),
        ('session_timeout_minutes', '30', 'Session timeout in minutes', 'session'),
        ('auto_mark_late_threshold', '10', 'Minutes after start time to mark as late', 'attendance'),
        ('max_session_duration', '180', 'Maximum session duration in minutes', 'session'),
        ('camera_quality_threshold', '720', 'Minimum camera quality requirement', 'camera'),
        ('notification_retention_days', '30', 'Days to keep notifications', 'notifications'),
        ('system_metrics_retention_days', '90', 'Days to keep system metrics', 'metrics'),
        ('auto_refresh_interval', '30', 'Dashboard auto-refresh interval in seconds', 'dashboard'),
        ('attendance_report_limit', '1000', 'Maximum records in attendance report', 'reports'),
        ('face_encoding_version', '1.0', 'Face encoding algorithm version', 'face_recognition'),
        ('cache_default_timeout', '300', 'Default cache timeout in seconds', 'performance'),
        ('enable_redis_cache', '1', 'Enable Redis caching', 'performance'),
    ]
    
    for key, value, desc, category in default_settings:
        setting = Settings(
            setting_key=key,
            setting_value=value,
            description=desc,
            category=category,
            is_system=1
        )
        db.session.add(setting)
    
    db.session.commit()
    print(f"✅ {len(default_settings)} default settings inserted")

def insert_holidays():
    """Insert holidays"""
    print("\n📅 Inserting Holidays...")
    
    from app.models.holidays import Holiday
    
    # Check if holidays exist
    if Holiday.query.count() > 0:
        print("  ℹ️  Holidays already exist")
        return
    
    for holiday_data in HOLIDAYS:
        holiday = Holiday(
            name=holiday_data["name"],
            date=datetime.strptime(holiday_data["date"], "%Y-%m-%d").date(),
            description=f"{holiday_data['name']} - Public Holiday",
            is_recurring=holiday_data["recurring"]
        )
        db.session.add(holiday)
        print(f"  ✓ {holiday_data['name']} - {holiday_data['date']}")
    
    db.session.commit()
    print(f"✅ {len(HOLIDAYS)} holidays inserted")

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT 1: COURSES & INSTRUCTORS")
    print("=" * 70)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Clear existing data
            clear_existing_data()
            
            # Generate data
            courses = generate_courses()
            instructors = generate_instructors()
            assignments = assign_instructors_to_courses(instructors, courses)
            
            # Create admin and insert system data
            create_admin_account()
            insert_default_settings()
            insert_holidays()
            
            # Summary
            print("\n" + "=" * 70)
            print("✅ DATA GENERATION COMPLETE!")
            print("=" * 70)
            print(f"📚 Courses: {len(courses)}")
            print(f"👨‍🏫 Instructors: {len(instructors)}")
            print(f"🔗 Instructor-Course Assignments: {len(assignments)}")
            print(f"🔐 Admin Account: Created")
            print(f"⚙️  System Settings: Configured")
            print(f"📅 Holidays: Configured")
            print("\n🔑 INSTRUCTOR LOGIN CREDENTIALS:")
            print("-" * 70)
            
            for instructor in instructors[:5]:  # Show first 5
                print(f"  ID: {instructor.instructor_id} | Password: {instructor.instructor_id}")
            
            if len(instructors) > 5:
                print(f"  ... and {len(instructors) - 5} more")
            
            print("\n⚠️  Default password is the instructor_id. Change on first login!")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()