"""
Generate instructor data using ORM
"""
import sys
import os
from datetime import datetime

# Set up paths to import from lec_panel
current_dir = os.path.dirname(os.path.abspath(__file__))  # faker folder
project_root = os.path.dirname(current_dir)  # attendance system folder
lec_panel_dir = os.path.join(project_root, 'lec_panel')  # lec_panel folder

# Add to path
sys.path.insert(0, lec_panel_dir)
sys.path.insert(0, current_dir)

# Import from lec_panel
from app import create_app, db
from app.models.user import Instructor

# Import faker config and utils
from faker_config import *
from faker_utils import generate_kenyan_name, generate_email, generate_kenyan_phone

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

def generate_instructors_data():
    """Generate instructor data using ORM"""
    print("=" * 50)
    print("GENERATING INSTRUCTORS")
    print("=" * 50)
    
    num_instructors = calculate_required_instructors()
    print(f"Generating {num_instructors} instructors...")
    
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
            
            # Create Instructor object using ORM
            instructor = Instructor(
                instructor_id=instructor_id,
                instructor_name=full_name,
                email=email,
                phone=phone,
                faculty=FACULTY,
                is_active=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_login=None
            )
            
            # Use model's set_password method (proper hashing)
            instructor.set_password(instructor_id)
            
            instructors_data.append(instructor)
            db.session.add(instructor)
            
            print(f"  ✓ {instructor_id}: {full_name} ({email})")
    
    # Commit all at once
    db.session.commit()
    
    print(f"\n✓ Successfully generated {len(instructors_data)} instructors")
    return instructors_data

def main():
    """Main execution with Flask app context"""
    app = create_app()
    
    with app.app_context():
        try:
            instructors = generate_instructors_data()
            
            print("\n" + "=" * 50)
            print("✓ GENERATION COMPLETE!")
            print("=" * 50)
            print(f"👨‍🏫 Total Instructors: {len(instructors)}")
            print("\n⚠️  Default password is the instructor_id")
            print("=" * 50)
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()