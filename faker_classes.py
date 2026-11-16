"""
Faker Script: Classes and Timetables
Generates classes for all courses (Years 1-4) and creates realistic timetables
Includes holiday management
Run this AFTER faker script that creates courses and instructors
"""

import sqlite3
import random
from datetime import datetime, date, timedelta
from faker.faker_config import (
    COURSES, TIME_SLOTS, WEEKDAYS, DAY_NAMES,
    generate_class_id, get_class_code, CURRENT_SEMESTER,
    COURSE_NAMES, HOLIDAYS, is_holiday, is_weekend,
    get_date_range_for_semester, get_weekdays_in_range
)

# Constants
DATABASE_PATH = "attendance.db"  # Update this to your actual database path

def create_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def clear_existing_data(conn):
    """Clear existing classes, timetables, and holidays"""
    print("\n🗑️  Clearing existing class data...")
    
    try:
        cursor = conn.cursor()
        
        # Delete in correct order to respect foreign keys
        cursor.execute("DELETE FROM timetable")
        cursor.execute("DELETE FROM class_instructors")
        cursor.execute("DELETE FROM class_courses")
        cursor.execute("DELETE FROM classes")
        cursor.execute("DELETE FROM holidays")
        
        conn.commit()
        print("✅ Existing class data cleared")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Error clearing data: {e}")
        return False

def insert_holidays(conn):
    """Insert holiday data into the database"""
    print("\n🎉 Inserting Holidays...")
    
    try:
        cursor = conn.cursor()
        
        holidays_inserted = 0
        for holiday in HOLIDAYS:
            cursor.execute("""
                INSERT INTO holidays (name, date, description, is_recurring, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                holiday["name"],
                holiday["date"],
                f"Public holiday: {holiday['name']}",
                1 if holiday["recurring"] else 0,
                datetime.utcnow()
            ))
            holidays_inserted += 1
        
        conn.commit()
        print(f"✅ {holidays_inserted} holidays inserted")
        return holidays_inserted
    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Error inserting holidays: {e}")
        return 0

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

def generate_classes(conn):
    """Generate classes for all courses across all years"""
    print("\n🏫 Generating Classes...")
    
    cursor = conn.cursor()
    classes = []
    used_names = set()  # Track used class names globally
    used_class_ids = set()  # Track used class IDs to ensure uniqueness
    
    for course_code, course_info in COURSES.items():
        num_years = course_info["years"]
        dept_prefix = course_info["code_prefix"]
        
        print(f"\n  Course: {course_code} - {course_info['name']}")
        
        # Generate classes for each year
        for year in range(1, num_years + 1):
            # Generate for both semesters (1.1 and 1.2, 2.1 and 2.2, etc.)
            for sem_part in [1, 2]:
                semester = f"{year}.{sem_part}"
                
                # Each year/semester has 5-7 different classes
                num_classes = random.randint(5, 7)
                
                for class_idx in range(num_classes):
                    # Generate unique class ID in format: PREFIX YXX (e.g., SCI 231, COMP 122)
                    while True:
                        class_number = f"{year}{random.randint(0, 9)}{random.randint(0, 9)}"
                        class_id = f"{dept_prefix} {class_number}"
                        
                        if class_id not in used_class_ids:
                            used_class_ids.add(class_id)
                            break
                    
                    # Get a unique class name (just the descriptive name, no code prefix)
                    class_name = generate_unique_class_name(course_code, year, semester, used_names)
                    
                    # Insert into classes table
                    try:
                        cursor.execute("""
                            INSERT INTO classes (class_id, course_code, class_name, year, semester, 
                                               is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            class_id,
                            course_code,
                            class_name,  # Just the descriptive name like "Advancements in Biology"
                            year,
                            semester,
                            1,  # is_active
                            datetime.utcnow(),
                            datetime.utcnow()
                        ))
                        
                        # Also insert into class_courses junction table
                        cursor.execute("""
                            INSERT INTO class_courses (class_id, course_code)
                            VALUES (?, ?)
                        """, (class_id, course_code))
                        
                        classes.append({
                            'class_id': class_id,
                            'course_code': course_code,
                            'class_name': class_name,  # Just the descriptive name
                            'year': year,
                            'semester': semester
                        })
                        
                        if len(classes) % 20 == 0:
                            print(f"    Generated {len(classes)} classes...")
                            
                    except sqlite3.Error as e:
                        print(f"    ⚠️  Error inserting class {class_id}: {e}")
                        continue
    
    conn.commit()
    print(f"\n✅ {len(classes)} classes created")
    return classes

def assign_instructors_to_classes(conn, classes):
    """Assign instructors to classes"""
    print("\n🔗 Assigning Instructors to Classes...")
    
    cursor = conn.cursor()
    assignments = []
    
    for class_obj in classes:
        # Get instructors who teach this course
        cursor.execute("""
            SELECT i.instructor_id, i.instructor_name
            FROM instructors i
            JOIN instructor_courses ic ON i.instructor_id = ic.instructor_id
            WHERE ic.course_code = ?
        """, (class_obj['course_code'],))
        
        course_instructors = cursor.fetchall()
        
        if not course_instructors:
            print(f"  ⚠️  No instructors found for {class_obj['course_code']}")
            continue
        
        # Assign 1-2 instructors per class
        num_to_assign = min(random.randint(1, 2), len(course_instructors))
        selected = random.sample(course_instructors, num_to_assign)
        
        for instructor in selected:
            # Check if already assigned
            cursor.execute("""
                SELECT COUNT(*) FROM class_instructors 
                WHERE class_id = ? AND instructor_id = ?
            """, (class_obj['class_id'], instructor['instructor_id']))
            
            if cursor.fetchone()[0] > 0:
                continue
            
            try:
                cursor.execute("""
                    INSERT INTO class_instructors (class_id, instructor_id, assigned_date)
                    VALUES (?, ?, ?)
                """, (
                    class_obj['class_id'],
                    instructor['instructor_id'],
                    date.today()
                ))
                
                assignments.append({
                    'class_id': class_obj['class_id'],
                    'instructor_id': instructor['instructor_id']
                })
                
                print(f"  ✓ {instructor['instructor_name']} → {class_obj['class_name']}")
                
            except sqlite3.Error as e:
                print(f"  ⚠️  Error assigning instructor: {e}")
                continue
    
    conn.commit()
    print(f"✅ {len(assignments)} class-instructor assignments created")
    return assignments

def generate_timetables(conn, classes):
    """Generate realistic timetables for all classes"""
    print("\n📅 Generating Timetables...")
    
    cursor = conn.cursor()
    timetables = []
    used_slots = {}  # Track used time slots per day per year/semester to avoid conflicts
    
    for class_obj in classes:
        # Each class typically has 2-3 sessions per week
        num_sessions = random.randint(2, 3)
        
        # Track key for conflict detection: course + year + semester
        conflict_key = f"{class_obj['course_code']}-Y{class_obj['year']}-{class_obj['semester']}"
        
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
                print(f"  ⚠️  No available slots for {class_obj['class_name']} on {DAY_NAMES[day]}")
                continue
            
            # Select a time slot
            time_slot = random.choice(available_slots)
            start_time, end_time = time_slot
            
            # Mark this slot as used
            used_slots[conflict_key][day].append(time_slot)
            
            # Insert timetable entry
            try:
                cursor.execute("""
                    INSERT INTO timetable (class_id, day_of_week, start_time, end_time, 
                                         is_active, effective_from)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    class_obj['class_id'],
                    day,
                    start_time,
                    end_time,
                    1,  # is_active (using INTEGER for SQLite BOOLEAN)
                    date.today()
                ))
                
                timetables.append({
                    'class_id': class_obj['class_id'],
                    'day_of_week': day,
                    'start_time': start_time,
                    'end_time': end_time
                })
                
                class_name_short = class_obj['class_name'][:50]
                print(f"  ✓ {class_name_short}... | {DAY_NAMES[day]} {start_time}-{end_time}")
                
            except sqlite3.Error as e:
                print(f"  ⚠️  Error inserting timetable: {e}")
                continue
    
    conn.commit()
    print(f"✅ {len(timetables)} timetable entries created")
    return timetables

def verify_no_conflicts(conn):
    """Verify there are no timetable conflicts for students"""
    print("\n🔍 Verifying No Timetable Conflicts...")
    
    cursor = conn.cursor()
    conflicts_found = []
    
    # Get all active timetables with class info
    cursor.execute("""
        SELECT t.*, c.course_code, c.class_name, c.year, c.semester
        FROM timetable t
        JOIN classes c ON t.class_id = c.class_id
        WHERE t.is_active = 1
        ORDER BY c.course_code, c.year, c.semester, t.day_of_week, t.start_time
    """)
    
    timetables = cursor.fetchall()
    
    # Group timetables by course, year, semester
    grouped = {}
    for tt in timetables:
        key = f"{tt['course_code']}-Y{tt['year']}-{tt['semester']}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(tt)
    
    # Check each group for time conflicts
    for group_key, group_timetables in grouped.items():
        for i, tt1 in enumerate(group_timetables):
            for tt2 in group_timetables[i+1:]:
                # Same day?
                if tt1['day_of_week'] == tt2['day_of_week']:
                    # Check time overlap
                    start1 = datetime.strptime(tt1['start_time'], '%H:%M').time()
                    end1 = datetime.strptime(tt1['end_time'], '%H:%M').time()
                    start2 = datetime.strptime(tt2['start_time'], '%H:%M').time()
                    end2 = datetime.strptime(tt2['end_time'], '%H:%M').time()
                    
                    if (start1 < end2 and end1 > start2):
                        conflict = {
                            'group': group_key,
                            'day': DAY_NAMES[tt1['day_of_week']],
                            'class1': tt1['class_name'],
                            'time1': f"{tt1['start_time']}-{tt1['end_time']}",
                            'class2': tt2['class_name'],
                            'time2': f"{tt2['start_time']}-{tt2['end_time']}"
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

def print_sample_timetable(conn):
    """Print a sample week schedule for one class"""
    print("\n📋 Sample Weekly Timetable (First Class):")
    print("-" * 70)
    
    cursor = conn.cursor()
    
    # Get first class
    cursor.execute("SELECT * FROM classes LIMIT 1")
    first_class = cursor.fetchone()
    
    if not first_class:
        print("  No classes found")
        return
    
    # Get timetables for this class
    cursor.execute("""
        SELECT * FROM timetable
        WHERE class_id = ? AND is_active = 1
        ORDER BY day_of_week, start_time
    """, (first_class['class_id'],))
    
    timetables = cursor.fetchall()
    
    print(f"Class: {first_class['class_name']}")
    print(f"Course: {first_class['course_code']} | Year: {first_class['year']} | Semester: {first_class['semester']}")
    print()
    
    for tt in timetables:
        print(f"  {DAY_NAMES[tt['day_of_week']]:10} | {tt['start_time']} - {tt['end_time']}")
    
    print("-" * 70)

def print_statistics(conn):
    """Print database statistics"""
    print("\n📊 Database Statistics:")
    print("-" * 70)
    
    cursor = conn.cursor()
    
    # Count classes
    cursor.execute("SELECT COUNT(*) as count FROM classes")
    class_count = cursor.fetchone()['count']
    print(f"  Total Classes: {class_count}")
    
    # Count timetables
    cursor.execute("SELECT COUNT(*) as count FROM timetable")
    timetable_count = cursor.fetchone()['count']
    print(f"  Total Timetable Entries: {timetable_count}")
    
    # Count class-instructor assignments
    cursor.execute("SELECT COUNT(*) as count FROM class_instructors")
    assignment_count = cursor.fetchone()['count']
    print(f"  Total Class-Instructor Assignments: {assignment_count}")
    
    # Count holidays
    cursor.execute("SELECT COUNT(*) as count FROM holidays")
    holiday_count = cursor.fetchone()['count']
    print(f"  Total Holidays: {holiday_count}")
    
    # Classes per course
    cursor.execute("""
        SELECT course_code, COUNT(*) as count 
        FROM classes 
        GROUP BY course_code
        ORDER BY course_code
    """)
    print("\n  Classes per Course:")
    for row in cursor.fetchall():
        print(f"    {row['course_code']}: {row['count']} classes")
    
    print("-" * 70)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT: CLASSES & TIMETABLES")
    print("=" * 70)
    
    conn = create_connection()
    if conn is None:
        print("❌ Failed to connect to database")
        return
    
    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Verify instructors and courses exist
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM instructors")
        instructor_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM courses")
        course_count = cursor.fetchone()['count']
        
        if instructor_count == 0 or course_count == 0:
            print("\n❌ ERROR: Please run the courses and instructors faker script first!")
            return
        
        print(f"\n✓ Found {instructor_count} instructors and {course_count} courses")
        
        # Clear existing data
        if not clear_existing_data(conn):
            return
        
        # Insert holidays
        holidays_count = insert_holidays(conn)
        
        # Generate data
        classes = generate_classes(conn)
        assignments = assign_instructors_to_classes(conn, classes)
        timetables = generate_timetables(conn, classes)
        
        # Verify
        conflicts = verify_no_conflicts(conn)
        
        # Show sample
        print_sample_timetable(conn)
        
        # Show statistics
        print_statistics(conn)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ DATA GENERATION COMPLETE!")
        print("=" * 70)
        print(f"🏫 Classes: {len(classes)}")
        print(f"🔗 Class-Instructor Assignments: {len(assignments)}")
        print(f"📅 Timetable Entries: {len(timetables)}")
        print(f"🎉 Holidays: {holidays_count}")
        print(f"⚠️  Conflicts: {len(conflicts)}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()