"""
Generate class data with proper semester distribution
Semester format: 1 or 2
Year_level format: 4.2 (year 4, semester 2)
Class ID format: COMP 123, STAT 421 (prefix + year + sequential number)
"""
import sqlite3
import random
from faker_config import *
from faker_utils import *
from datetime import datetime

def generate_classes_data(db_path=DB_PATH):
    """Generate class data for all courses and years"""
    print("=" * 50)
    print("GENERATING CLASSES")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    classes_data = []
    class_counter = 1
    
    for course_code, course_info in COURSES.items():
        print(f"\n{course_code} - {course_info['name']}")
        prefix = course_info['code_prefix']
        
        # Get available class names for this course
        course_class_names = COURSE_NAMES.get(course_code, {})
        
        for year_level in range(1, 5):  # Years 1-4
            print(f"\n  Year {year_level}:")
            
            # Get class names for this year
            year_class_names = course_class_names.get(year_level, [])
            
            if not year_class_names:
                print(f"    ⚠ No classes defined for year {year_level}")
                continue
            
            # Split classes between semesters (6 per semester = 12 total per year)
            semester_1_classes = year_class_names[:6]
            semester_2_classes = year_class_names[6:12]
            
            # Generate Semester 1 classes
            for idx, class_name in enumerate(semester_1_classes, 1):
                # Format: PREFIX YXX (e.g., COMP 101, STAT 201)
                class_id = f"{prefix} {year_level}{idx:02d}"
                
                class_data = {
                    'class_id': class_id,
                    'course_code': course_code,
                    'class_name': class_name,
                    'year': year_level,
                    'year_level': make_year_level(year_level, 1),  # e.g., "1.1"
                    'semester': 1,
                    'created_at': format_datetime_for_db(datetime.now()),
                    'updated_at': format_datetime_for_db(datetime.now()),
                    'is_active': 1
                }
                
                classes_data.append(class_data)
                print(f"    ✓ {class_id}: {class_name} (Sem 1, Year Level {class_data['year_level']})")
            
            # Generate Semester 2 classes
            for idx, class_name in enumerate(semester_2_classes, 7):
                # Format: PREFIX YXX (e.g., COMP 107, STAT 207)
                class_id = f"{prefix} {year_level}{idx:02d}"
                
                class_data = {
                    'class_id': class_id,
                    'course_code': course_code,
                    'class_name': class_name,
                    'year': year_level,
                    'year_level': make_year_level(year_level, 2),  # e.g., "1.2"
                    'semester': 2,
                    'created_at': format_datetime_for_db(datetime.now()),
                    'updated_at': format_datetime_for_db(datetime.now()),
                    'is_active': 1
                }
                
                classes_data.append(class_data)
                print(f"    ✓ {class_id}: {class_name} (Sem 2, Year Level {class_data['year_level']})")
    
    # Insert into database
    cursor.executemany("""
        INSERT OR REPLACE INTO classes 
        (class_id, course_code, class_name, year, year_level, semester, 
         created_at, updated_at, is_active)
        VALUES (:class_id, :course_code, :class_name, :year, :year_level, :semester,
                :created_at, :updated_at, :is_active)
    """, classes_data)
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Successfully generated {len(classes_data)} classes")
    return classes_data

if __name__ == "__main__":
    generate_classes_data()