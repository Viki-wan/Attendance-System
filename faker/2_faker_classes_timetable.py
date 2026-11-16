"""
Faker Script 2: Classes and Timetables
Generates classes for all courses (Years 1-4) and creates realistic timetables
Run this AFTER faker_courses_instructors.py
"""

import sys
import os
from datetime import datetime, date
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

from app import create_app, db
from app.models.class_model import Class, ClassInstructor
from app.models.course import Course
from app.models.user import Instructor
from app.models.timetable import Timetable
from faker_config import (
    COURSES, TIME_SLOTS, WEEKDAYS, DAY_NAMES,
    generate_class_id, get_class_code, CURRENT_SEMESTER, SEMESTERS,
    COURSE_NAMES
)

def generate_unique_class_name(course_code, year, semester, used_names):
    """Generate a unique class name for the course, year, and semester"""
    # Get available class names for this course and year
    available_names = COURSE_NAMES.get(course_code, {}).get(year, [])
    
    if not available_names:
        # Fallback to generic names if course not in COURSE_NAMES
        available_names = [f"Class {i+1}" for i in range(20)]
    
    # Try to find an unused name
    for name in available_names:
        full_key = f"{course_code}-Y{year}-{name}"
        if full_key not in used_names:
            used_names.add(full_key)
            return name
    
    # If all names are used, generate a numbered variant
    base_name = available_names[0] if available_names else "Class"
    counter = 1
    while True:
        name = f"{base_name} ({counter})"
        full_key = f"{course_code}-Y{year}-{name}"
        if full_key not in used_names:
            used_names.add(full_key)
            return name
        counter += 1

def clear_existing_data():
    """Clear existing classes and timetables"""
    print("\n🗑️  Clearing existing class data...")
    
    try:
        Timetable.query.delete()
        ClassInstructor.query.delete()
        Class.query.delete()
        
        db.session.commit()
        print("✅ Existing class data cleared")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing data: {e}")
        raise

def generate_classes():
    """Generate classes for all courses across all years"""
    print("\n🏫 Generating Classes...")
    
    classes = []
    used_names = set()  # Track used class names globally
    
    for course_code, course_info in COURSES.items():
        num_years = course_info["years"]
        
        print(f"\n  Course: {course_code} - {course_info['name']}")
        
        # Generate classes for each year
        for year in range(1, num_years + 1):
            # Generate for both semesters (1.1 and 1.2, 2.1 and 2.2, etc.)
            for sem_part in [1, 2]:
                semester = f"{year}.{sem_part}"
                
                # Each year/semester has 5-7 different classes
                num_classes = random.randint(5, 7)
                
                for class_idx in range(num_classes):
                    # Generate unique class ID: COURSE-YEAR-SEMESTER-INDEX
                    class_id = f"{course_code}-Y{year}-S{semester}-C{class_idx + 1}"
                    
                    # Generate class code (e.g., COMP122, STAT181)
                    class_code_str = get_class_code(course_code, class_idx + 1, year)
                    
                    # Get a unique class name
                    class_name = generate_unique_class_name(course_code, year, semester, used_names)
                    
                    # Full class name with code
                    full_class_name = f"{class_code_str}: {class_name}"
                    
                    new_class = Class(
                        class_id=class_id,
                        course_code=course_code,
                        class_name=full_class_name,
                        year=year,
                        semester=semester,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    classes.append(new_class)
                    db.session.add(new_class)
                    
                    if len(classes) % 20 == 0:
                        print(f"    Generated {len(classes)} classes...")
    
    db.session.commit()
    print(f"\n✅ {len(classes)} classes created")
    return classes

def assign_instructors_to_classes(classes):
    """Assign instructors to classes"""
    print("\n🔗 Assigning Instructors to Classes...")
    
    assignments = []
    
    for class_obj in classes:
        # Get instructors who teach this course
        from app.models.course import InstructorCourse
        
        course_instructors = db.session.query(Instructor).join(
            InstructorCourse
        ).filter(
            InstructorCourse.course_code == class_obj.course_code
        ).all()
        
        if not course_instructors:
            print(f"  ⚠️  No instructors found for {class_obj.course_code}")
            continue
        
        # Assign 1-2 instructors per class
        num_to_assign = min(random.randint(1, 2), len(course_instructors))
        selected = random.sample(course_instructors, num_to_assign)
        
        for instructor in selected:
            # Check if already assigned
            existing = ClassInstructor.query.filter_by(
                class_id=class_obj.class_id,
                instructor_id=instructor.instructor_id
            ).first()
            
            if existing:
                continue
            
            assignment = ClassInstructor(
                class_id=class_obj.class_id,
                instructor_id=instructor.instructor_id,
                assigned_date=date.today()
            )
            
            assignments.append(assignment)
            db.session.add(assignment)
            
            print(f"  ✓ {instructor.instructor_name} → {class_obj.class_name}")
    
    db.session.commit()
    print(f"✅ {len(assignments)} class-instructor assignments created")
    return assignments

def generate_timetables(classes):
    """Generate realistic timetables for all classes"""
    print("\n📅 Generating Timetables...")
    
    timetables = []
    used_slots = {}  # Track used time slots per day per year/semester to avoid conflicts
    
    for class_obj in classes:
        # Each class typically has 2-3 sessions per week
        num_sessions = random.randint(2, 3)
        
        # Track key for conflict detection: course + year + semester
        conflict_key = f"{class_obj.course_code}-Y{class_obj.year}-{class_obj.semester}"
        
        if conflict_key not in used_slots:
            used_slots[conflict_key] = {}
        
        # Select random days for this class
        available_days = WEEKDAYS.copy()
        selected_days = random.sample(available_days, num_sessions)
        
        for day in selected_days:
            # Initialize day tracking if not exists
            if day not in used_slots[conflict_key]:
                used_slots[conflict_key][day] = []
            
            # Find an available time slot
            available_slots = [
                slot for slot in TIME_SLOTS 
                if slot not in used_slots[conflict_key][day]
            ]
            
            if not available_slots:
                print(f"  ⚠️  No available slots for {class_obj.class_name} on {DAY_NAMES[day]}")
                continue
            
            # Select a time slot
            time_slot = random.choice(available_slots)
            start_time, end_time = time_slot
            
            # Mark this slot as used
            used_slots[conflict_key][day].append(time_slot)
            
            # Create timetable entry
            timetable = Timetable(
                class_id=class_obj.class_id,
                day_of_week=day,
                start_time=start_time,
                end_time=end_time,
                is_active=True,
                effective_from=date.today()
            )
            
            timetables.append(timetable)
            db.session.add(timetable)
            
            print(f"  ✓ {class_obj.class_name[:50]}... | {DAY_NAMES[day]} {start_time}-{end_time}")
    
    db.session.commit()
    print(f"✅ {len(timetables)} timetable entries created")
    return timetables

def verify_no_conflicts():
    """Verify there are no timetable conflicts for students"""
    print("\n🔍 Verifying No Timetable Conflicts...")
    
    conflicts_found = []
    
    # Group timetables by course, year, semester
    timetables = Timetable.query.join(Class).filter(Timetable.is_active == True).all()
    
    grouped = {}
    for tt in timetables:
        key = f"{tt.class_.course_code}-Y{tt.class_.year}-{tt.class_.semester}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(tt)
    
    # Check each group for time conflicts
    for group_key, group_timetables in grouped.items():
        for i, tt1 in enumerate(group_timetables):
            for tt2 in group_timetables[i+1:]:
                # Same day?
                if tt1.day_of_week == tt2.day_of_week:
                    # Check time overlap
                    start1 = datetime.strptime(tt1.start_time, '%H:%M').time()
                    end1 = datetime.strptime(tt1.end_time, '%H:%M').time()
                    start2 = datetime.strptime(tt2.start_time, '%H:%M').time()
                    end2 = datetime.strptime(tt2.end_time, '%H:%M').time()
                    
                    if (start1 < end2 and end1 > start2):
                        conflict = {
                            'group': group_key,
                            'day': DAY_NAMES[tt1.day_of_week],
                            'class1': tt1.class_.class_name,
                            'time1': f"{tt1.start_time}-{tt1.end_time}",
                            'class2': tt2.class_.class_name,
                            'time2': f"{tt2.start_time}-{tt2.end_time}"
                        }
                        conflicts_found.append(conflict)
    
    if conflicts_found:
        print(f"  ⚠️  Found {len(conflicts_found)} conflicts!")
        for conflict in conflicts_found[:5]:  # Show first 5
            print(f"    - {conflict['group']} on {conflict['day']}:")
            print(f"      {conflict['class1']} ({conflict['time1']})")
            print(f"      {conflict['class2']} ({conflict['time2']})")
    else:
        print("  ✅ No conflicts found! All timetables are valid.")
    
    return conflicts_found

def print_sample_timetable():
    """Print a sample week schedule for one class"""
    print("\n📋 Sample Weekly Timetable (First Class):")
    print("-" * 70)
    
    first_class = Class.query.first()
    if not first_class:
        print("  No classes found")
        return
    
    timetables = Timetable.query.filter_by(
        class_id=first_class.class_id,
        is_active=True
    ).order_by(Timetable.day_of_week, Timetable.start_time).all()
    
    print(f"Class: {first_class.class_name}")
    print(f"Course: {first_class.course_code} | Year: {first_class.year} | Semester: {first_class.semester}")
    print()
    
    for tt in timetables:
        print(f"  {DAY_NAMES[tt.day_of_week]:10} | {tt.start_time} - {tt.end_time}")
    
    print("-" * 70)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT 2: CLASSES & TIMETABLES")
    print("=" * 70)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Verify instructors and courses exist
            instructor_count = Instructor.query.count()
            course_count = Course.query.count()
            
            if instructor_count == 0 or course_count == 0:
                print("\n❌ ERROR: Please run faker_courses_instructors.py first!")
                return
            
            print(f"\n✓ Found {instructor_count} instructors and {course_count} courses")
            
            # Clear existing data
            clear_existing_data()
            
            # Generate data
            classes = generate_classes()
            assignments = assign_instructors_to_classes(classes)
            timetables = generate_timetables(classes)
            
            # Verify
            conflicts = verify_no_conflicts()
            
            # Show sample
            print_sample_timetable()
            
            # Summary
            print("\n" + "=" * 70)
            print("✅ DATA GENERATION COMPLETE!")
            print("=" * 70)
            print(f"🏫 Classes: {len(classes)}")
            print(f"🔗 Class-Instructor Assignments: {len(assignments)}")
            print(f"📅 Timetable Entries: {len(timetables)}")
            print(f"⚠️  Conflicts: {len(conflicts)}")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()