"""
Generate class enrollments for students
Auto-enrolls students based on their course, year, and current semester
Also handles repeat enrollments for some students
"""
import sqlite3
import random
from faker_config import *
from faker_utils import *
from datetime import datetime

def generate_class_enrollments(db_path=DB_PATH):
    """
    Generate class enrollments for all students
    Note: This should be run AFTER students are added to the database
    """
    print("=" * 50)
    print("GENERATING CLASS ENROLLMENTS")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if there are students in the database
    cursor.execute("SELECT COUNT(*) FROM students")
    student_count = cursor.fetchone()[0]
    
    if student_count == 0:
        print("\n⚠️  No students found in database!")
        print("    This script should be run after student data is added.")
        print("    Skipping enrollment generation...")
        conn.close()
        return []
    
    print(f"Found {student_count} students in database\n")
    
    # Get all students with their course and year info
    cursor.execute("""
        SELECT student_id, course, year_of_study, current_semester
        FROM students
        WHERE is_active = 1
    """)
    students = cursor.fetchall()
    
    # Get all classes
    cursor.execute("""
        SELECT class_id, course_code, year, semester, class_name
        FROM classes
        WHERE is_active = 1
    """)
    all_classes = cursor.fetchall()
    
    # Group classes by course, year, and semester for efficient lookup
    classes_by_key = {}
    for class_data in all_classes:
        class_id, course_code, year, semester, class_name = class_data
        key = (course_code, year, semester)
        if key not in classes_by_key:
            classes_by_key[key] = []
        classes_by_key[key].append(class_data)
    
    enrollments_data = []
    
    # Get current semester for academic year determination
    current_semester = get_current_semester()
    
    # Enroll each student in their appropriate classes
    for student_data in students:
        student_id, course, year_of_study, student_semester = student_data
        
        # Parse student semester (could be "1.1", "1.2", etc. or just 1, 2)
        if isinstance(student_semester, str):
            # Extract just the semester part (1 or 2)
            if '.' in student_semester:
                semester_num = int(student_semester.split('.')[1])
            else:
                semester_num = int(student_semester)
        else:
            semester_num = student_semester
        
        # Find classes for this student (course + year + semester)
        key = (course, year_of_study, semester_num)
        student_classes = classes_by_key.get(key, [])
        
        if not student_classes:
            print(f"⚠️  No classes found for {student_id} ({course}, Year {year_of_study}, Sem {semester_num})")
            continue
        
        # Enroll in all appropriate classes
        for class_data in student_classes:
            class_id, course_code, year, semester, class_name = class_data
            
            enrollment = {
                'student_id': student_id,
                'class_id': class_id,
                'semester': semester_num,
                'academic_year': ACADEMIC_YEAR,
                'enrollment_date': format_date_for_db(datetime.now()),
                'status': 'active',
                'created_at': format_datetime_for_db(datetime.now()),
                'updated_at': format_datetime_for_db(datetime.now())
            }
            
            enrollments_data.append(enrollment)
        
        print(f"✓ {student_id}: Enrolled in {len(student_classes)} classes (Year {year_of_study}, Sem {semester_num})")
    
    # Simulate some repeat enrollments (5% of students have 1-2 repeat classes)
    print("\nGenerating repeat enrollments (5% of students)...")
    num_repeaters = max(1, int(len(students) * 0.05))
    
    repeaters = random.sample(students, num_repeaters)
    
    for student_data in repeaters:
        student_id, course, year_of_study, student_semester = student_data
        
        # Parse semester
        if isinstance(student_semester, str):
            if '.' in student_semester:
                semester_num = int(student_semester.split('.')[1])
            else:
                semester_num = int(student_semester)
        else:
            semester_num = student_semester
        
        # They're repeating a class from their current year or previous year
        repeat_year = year_of_study if random.random() > 0.5 else max(1, year_of_study - 1)
        
        # Get classes from that year
        key = (course, repeat_year, semester_num)
        repeat_classes = classes_by_key.get(key, [])
        
        if repeat_classes:
            # Pick 1-2 classes to repeat
            num_repeats = random.randint(1, min(2, len(repeat_classes)))
            classes_to_repeat = random.sample(repeat_classes, num_repeats)
            
            for class_data in classes_to_repeat:
                class_id, course_code, year, semester, class_name = class_data
                
                # Check if already enrolled (don't create duplicate)
                existing = any(
                    e['student_id'] == student_id and e['class_id'] == class_id 
                    for e in enrollments_data
                )
                
                if not existing:
                    enrollment = {
                        'student_id': student_id,
                        'class_id': class_id,
                        'semester': semester_num,
                        'academic_year': ACADEMIC_YEAR,
                        'enrollment_date': format_date_for_db(datetime.now()),
                        'status': 'active',
                        'created_at': format_datetime_for_db(datetime.now()),
                        'updated_at': format_datetime_for_db(datetime.now())
                    }
                    
                    enrollments_data.append(enrollment)
                    print(f"  ↻ {student_id}: Repeating {class_name}")
    
    # Insert into database
    if enrollments_data:
        cursor.executemany("""
            INSERT OR IGNORE INTO class_enrollments 
            (student_id, class_id, semester, academic_year, enrollment_date, 
             status, created_at, updated_at)
            VALUES (:student_id, :class_id, :semester, :academic_year, :enrollment_date,
                    :status, :created_at, :updated_at)
        """, enrollments_data)
        
        conn.commit()
    
    # Print summary
    print(f"\n{'=' * 50}")
    print("ENROLLMENT SUMMARY")
    print(f"{'=' * 50}")
    
    cursor.execute("""
        SELECT 
            c.course_code,
            c.year,
            c.semester,
            COUNT(ce.id) as enrollment_count
        FROM class_enrollments ce
        JOIN classes c ON c.class_id = ce.class_id
        WHERE ce.status = 'active'
        GROUP BY c.course_code, c.year, c.semester
        ORDER BY c.course_code, c.year, c.semester
    """)
    
    summary = cursor.fetchall()
    for row in summary:
        course_code, year, semester, count = row
        print(f"{course_code} Year {year} Sem {semester}: {count} enrollments")
    
    # Update total_students count in class_sessions
    print("\nUpdating class session student counts...")
    cursor.execute("""
        UPDATE class_sessions
        SET total_students = (
            SELECT COUNT(DISTINCT ce.student_id)
            FROM class_enrollments ce
            WHERE ce.class_id = class_sessions.class_id
            AND ce.status = 'active'
        )
    """)
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Successfully generated {len(enrollments_data)} class enrollments")
    return enrollments_data

if __name__ == "__main__":
    generate_class_enrollments()