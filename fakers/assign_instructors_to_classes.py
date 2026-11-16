"""
Assign instructors to classes
Each instructor gets 2-5 classes, distributed across year levels
"""
import sqlite3
import random
from faker_config import *
from faker_utils import *
from datetime import datetime

def assign_instructors_to_classes(db_path=DB_PATH):
    """Assign instructors to classes"""
    print("=" * 50)
    print("ASSIGNING INSTRUCTORS TO CLASSES")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all instructors grouped by course
    cursor.execute("""
        SELECT instructor_id, instructor_name, faculty 
        FROM instructors 
        ORDER BY instructor_id
    """)
    all_instructors = cursor.fetchall()
    
    # Get all classes
    cursor.execute("""
        SELECT class_id, course_code, class_name, year_level, semester
        FROM classes
        ORDER BY course_code, year_level, semester
    """)
    all_classes = cursor.fetchall()
    
    # Group classes by course
    classes_by_course = {}
    for class_data in all_classes:
        course_code = class_data[1]
        if course_code not in classes_by_course:
            classes_by_course[course_code] = []
        classes_by_course[course_code].append(class_data)
    
    # Group instructors by course (divide them evenly)
    instructors_per_course = {}
    instructors_list = list(all_instructors)
    random.shuffle(instructors_list)
    
    chunk_size = len(instructors_list) // len(COURSES)
    for idx, course_code in enumerate(COURSES.keys()):
        start_idx = idx * chunk_size
        end_idx = start_idx + chunk_size if idx < len(COURSES) - 1 else len(instructors_list)
        instructors_per_course[course_code] = instructors_list[start_idx:end_idx]
    
    assignments = []
    instructor_courses_data = []
    class_instructors_data = []
    
    for course_code, instructors in instructors_per_course.items():
        print(f"\n{course_code}:")
        course_classes = classes_by_course.get(course_code, [])
        
        # Shuffle instructors for random assignment
        random.shuffle(instructors)
        
        # Track how many classes each instructor has
        instructor_class_count = {inst[0]: 0 for inst in instructors}
        
        # Assign each class to an instructor
        for class_data in course_classes:
            class_id, _, class_name, year_level, semester = class_data
            
            # Find instructor with fewest classes (and less than 5 classes)
            available_instructors = [
                inst_id for inst_id, count in instructor_class_count.items() 
                if count < 5
            ]
            
            if not available_instructors:
                # All instructors at max, cycle back
                available_instructors = list(instructor_class_count.keys())
            
            # Prefer instructors with fewer classes
            instructor_id = min(available_instructors, 
                              key=lambda x: instructor_class_count[x])
            
            instructor_name = next(i[1] for i in instructors if i[0] == instructor_id)
            instructor_class_count[instructor_id] += 1
            
            # Record assignment
            assignment = {
                'class_id': class_id,
                'instructor_id': instructor_id,
                'class_name': class_name,
                'instructor_name': instructor_name
            }
            assignments.append(assignment)
            
            # Prepare data for class_instructors table
            class_instructors_data.append({
                'class_id': class_id,
                'instructor_id': instructor_id,
                'assigned_date': format_date_for_db(datetime.now())
            })
            
            # Prepare data for instructor_courses table
            year = year_level
            instructor_courses_data.append({
                'instructor_id': instructor_id,
                'course_code': course_code,
                'semester': semester,
                'year': year,
                'is_coordinator': 0
            })
        
        # Print summary
        print(f"  Assigned {len(course_classes)} classes to {len(instructors)} instructors")
        for inst_id, count in instructor_class_count.items():
            inst_name = next(i[1] for i in instructors if i[0] == inst_id)
            print(f"    {inst_id} ({inst_name}): {count} classes")
    
    # Insert into class_instructors
    cursor.executemany("""
        INSERT OR REPLACE INTO class_instructors 
        (class_id, instructor_id, assigned_date)
        VALUES (:class_id, :instructor_id, :assigned_date)
    """, class_instructors_data)
    
    # Insert into instructor_courses (remove duplicates)
    unique_instructor_courses = []
    seen = set()
    for ic in instructor_courses_data:
        key = (ic['instructor_id'], ic['course_code'], ic['semester'], ic['year'])
        if key not in seen:
            seen.add(key)
            unique_instructor_courses.append(ic)
    
    cursor.executemany("""
        INSERT OR REPLACE INTO instructor_courses 
        (instructor_id, course_code, semester, year, is_coordinator)
        VALUES (:instructor_id, :course_code, :semester, :year, :is_coordinator)
    """, unique_instructor_courses)
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Successfully assigned {len(assignments)} classes to instructors")
    print(f"✓ Created {len(class_instructors_data)} class-instructor relationships")
    print(f"✓ Created {len(unique_instructor_courses)} instructor-course relationships")
    
    return assignments

if __name__ == "__main__":
    assign_instructors_to_classes()