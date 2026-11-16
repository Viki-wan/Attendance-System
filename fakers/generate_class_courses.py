"""
Generate class_courses junction table data
Links each class to its corresponding course
"""
import sqlite3
from faker_config import *
from faker_utils import format_datetime_for_db
from datetime import datetime

def generate_class_courses_data(db_path=DB_PATH):
    """Generate class-course relationships"""
    print("=" * 50)
    print("GENERATING CLASS-COURSE RELATIONSHIPS")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all existing classes
    cursor.execute("SELECT class_id, course_code FROM classes WHERE is_active = 1")
    classes = cursor.fetchall()
    
    if not classes:
        print("⚠️  No classes found. Please run generate_classes.py first.")
        conn.close()
        return []
    
    class_courses_data = []
    
    print(f"\nProcessing {len(classes)} classes...")
    
    for class_id, course_code in classes:
        # Each class belongs to one course (already defined in the class)
        class_course_data = {
            'class_id': class_id,
            'course_code': course_code
        }
        
        class_courses_data.append(class_course_data)
        print(f"  ✓ {class_id} → {course_code}")
    
    # Insert into database
    cursor.executemany("""
        INSERT OR REPLACE INTO class_courses 
        (class_id, course_code)
        VALUES (:class_id, :course_code)
    """, class_courses_data)
    
    conn.commit()
    
    # Verify the data
    cursor.execute("SELECT COUNT(*) FROM class_courses")
    count = cursor.fetchone()[0]
    
    print(f"\n{'='*50}")
    print(f"✓ Successfully generated {len(class_courses_data)} class-course relationships")
    print(f"✓ Total records in class_courses table: {count}")
    print(f"{'='*50}")
    
    # Show summary by course
    print("\nSummary by Course:")
    cursor.execute("""
        SELECT c.course_code, c.course_name, COUNT(cc.class_id) as class_count
        FROM courses c
        LEFT JOIN class_courses cc ON c.course_code = cc.course_code
        GROUP BY c.course_code
        ORDER BY c.course_code
    """)
    
    for course_code, course_name, class_count in cursor.fetchall():
        print(f"  {course_code}: {class_count} classes")
    
    conn.close()
    
    return class_courses_data

if __name__ == "__main__":
    generate_class_courses_data()