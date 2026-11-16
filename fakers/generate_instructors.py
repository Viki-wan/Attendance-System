"""
Generate instructor data
"""
import sqlite3
import random
from faker_config import *
from faker_utils import *
from datetime import datetime

def calculate_required_instructors():
    """
    Calculate how many instructors we need based on classes per year
    Each instructor handles 2-5 classes, with 12 classes per year per course
    """
    total_classes = 0
    
    for course_code in COURSES.keys():
        # 12 classes per year level (as per COURSE_NAMES structure)
        classes_per_year = 12
        years = 4
        total_classes += classes_per_year * years
    
    # Average 3-4 classes per instructor
    avg_classes_per_instructor = 3.5
    required_instructors = int(total_classes / avg_classes_per_instructor)
    
    return required_instructors

def generate_instructors_data(db_path=DB_PATH):
    """Generate instructor data"""
    print("=" * 50)
    print("GENERATING INSTRUCTORS")
    print("=" * 50)
    
    num_instructors = calculate_required_instructors()
    print(f"Generating {num_instructors} instructors...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    instructors_data = []
    used_names = set()
    used_emails = set()
    used_phones = set()
    
    instructor_number = INSTRUCTOR_START_NUMBER
    
    # Distribute instructors across courses
    instructors_per_course = num_instructors // len(COURSES)
    extra_instructors = num_instructors % len(COURSES)
    
    for idx, course_code in enumerate(COURSES.keys()):
        course_name = COURSES[course_code]['name']
        
        # Some courses get extra instructors
        num_for_this_course = instructors_per_course
        if idx < extra_instructors:
            num_for_this_course += 1
        
        print(f"\n{course_code} - {num_for_this_course} instructors")
        
        for i in range(num_for_this_course):
            # Generate unique name
            while True:
                first_name, last_name = generate_kenyan_name()
                full_name = f"{first_name} {last_name}"
                if full_name not in used_names:
                    used_names.add(full_name)
                    break
            
            # Generate unique email
            while True:
                email = generate_email(first_name, last_name, "university.ac.ke")
                if email not in used_emails:
                    used_emails.add(email)
                    break
            
            # Generate unique phone
            while True:
                phone = generate_kenyan_phone()
                if phone not in used_phones:
                    used_phones.add(phone)
                    break
            
            instructor_id = f"{INSTRUCTOR_ID_PREFIX}{instructor_number}"
            instructor_number += 1
            
            instructor = {
                'instructor_id': instructor_id,
                'instructor_name': full_name,
                'email': email,
                'phone': phone,
                'password': hash_password(instructor_id),  # Using instructor_id as default password
                'faculty': FACULTY,
                'created_at': format_datetime_for_db(datetime.now()),
                'updated_at': format_datetime_for_db(datetime.now()),
                'last_login': None,
                'is_active': 1
            }
            
            instructors_data.append(instructor)
            print(f"  âœ“ {instructor_id}: {full_name} ({email})")
    
    # Insert into database
    cursor.executemany("""
        INSERT OR REPLACE INTO instructors 
        (instructor_id, instructor_name, email, phone, password, faculty, 
         created_at, updated_at, last_login, is_active)
        VALUES (:instructor_id, :instructor_name, :email, :phone, :password, :faculty,
                :created_at, :updated_at, :last_login, :is_active)
    """, instructors_data)
    
    conn.commit()
    conn.close()
    
    print(f"\nâœ“ Successfully generated {len(instructors_data)} instructors")
    return instructors_data

if __name__ == "__main__":
    generate_instructors_data()