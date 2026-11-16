"""
Generate course data
"""
import sqlite3
from faker_config import *
from faker_utils import format_datetime_for_db
from datetime import datetime

def generate_courses_data(db_path=DB_PATH):
    """Generate and insert course data"""
    print("=" * 50)
    print("GENERATING COURSES")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    courses_data = []
    
    for course_code, course_info in COURSES.items():
        course_data = {
            'course_code': course_code,
            'course_name': course_info['name'],
            'faculty': FACULTY,
            'created_at': format_datetime_for_db(datetime.now()),
            'updated_at': format_datetime_for_db(datetime.now()),
            'is_active': 1
        }
        courses_data.append(course_data)
        
        print(f"✓ {course_code}: {course_info['name']}")
    
    # Insert into database
    cursor.executemany("""
        INSERT OR REPLACE INTO courses 
        (course_code, course_name, faculty, created_at, updated_at, is_active)
        VALUES (:course_code, :course_name, :faculty, :created_at, :updated_at, :is_active)
    """, courses_data)
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Successfully generated {len(courses_data)} courses")
    return courses_data

if __name__ == "__main__":
    generate_courses_data()