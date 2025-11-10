"""
Faker Script 3: Students with Face Encodings
Generates realistic students and assigns face encodings from sample images
Run this AFTER faker_classes_timetable.py
"""

import sys
import os
from datetime import datetime
import random
import pickle
import hashlib
from pathlib import Path

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

from app import create_app, db
from app.models.student import Student
from app.models.course import StudentCourse, Course
from faker_config import (
    COURSES, FIRST_NAMES, LAST_NAMES, CURRENT_YEAR, CURRENT_SEMESTER,
    generate_student_id, get_email, generate_phone, SEMESTERS
)

# Face recognition imports
try:
    import face_recognition
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    print("⚠️  face_recognition not available. Install with: pip install face-recognition")
    FACE_RECOGNITION_AVAILABLE = False

# Sample faces path - relative to project root
SAMPLE_FACES_PATH = os.path.join(project_root, "sample_faces")
# Uploads directories for storing student images
UPLOADS_DIR = os.path.join(lec_panel_dir, "uploads")
STUDENT_PHOTOS_DIR = os.path.join(UPLOADS_DIR, "student_photos")
FACE_ONLY_DIR = os.path.join(UPLOADS_DIR, "face_only")
FACE_ENCODINGS_DIR = os.path.join(UPLOADS_DIR, "face_encodings")

def ensure_directories():
    """Ensure all required directories exist"""
    for directory in [STUDENT_PHOTOS_DIR, FACE_ONLY_DIR, FACE_ENCODINGS_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"  ✓ Created directory: {directory}")

def clear_existing_data():
    """Clear existing students"""
    print("\n🗑️  Clearing existing student data...")
    
    try:
        StudentCourse.query.delete()
        Student.query.delete()
        
        db.session.commit()
        print("✅ Existing student data cleared")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing data: {e}")
        raise

def load_sample_faces():
    """Load all sample face images from the directory"""
    print(f"\n📸 Loading sample faces from: {SAMPLE_FACES_PATH}")
    
    if not os.path.exists(SAMPLE_FACES_PATH):
        print(f"  ⚠️  Directory not found: {SAMPLE_FACES_PATH}")
        return []
    
    face_files = []
    supported_formats = ['.jpg', '.jpeg', '.png', '.bmp']
    
    for file in Path(SAMPLE_FACES_PATH).iterdir():
        if file.suffix.lower() in supported_formats:
            face_files.append(str(file))
    
    print(f"  ✓ Found {len(face_files)} face images")
    return face_files

def extract_face(image_path, face_output_path):
    """Extract face from image and save to separate file"""
    try:
        # Load the image
        image = face_recognition.load_image_file(image_path)
        
        # Find face locations
        face_locations = face_recognition.face_locations(image)
        
        if not face_locations:
            print(f"    ⚠️  No face found in {os.path.basename(image_path)}")
            return None
            
        # Get the first face
        top, right, bottom, left = face_locations[0]
        
        # Add padding (20% of face width)
        face_width = right - left
        face_height = bottom - top
        pad_x = int(0.2 * face_width)
        pad_y = int(0.2 * face_height)
        
        # Ensure coordinates stay within image bounds
        left = max(0, left - pad_x)
        top = max(0, top - pad_y)
        right = min(image.shape[1], right + pad_x)
        bottom = min(image.shape[0], bottom + pad_y)
        
        # Extract face region
        face_img = image[top:bottom, left:right]
        
        # Save face image using PIL for better control
        face_pil = Image.fromarray(face_img)
        face_pil.save(face_output_path)
        
        return face_output_path
        
    except Exception as e:
        print(f"    ❌ Error extracting face: {e}")
        return None

def compute_image_hash(image_path, face_only_path=None):
    """Compute perceptual hash prioritizing face if available"""
    try:
        # If face extraction succeeded, use that for hashing
        if face_only_path and os.path.exists(face_only_path):
            try:
                face_image = Image.open(face_only_path).convert("L")
                face_image = ImageOps.exif_transpose(face_image)
                face_image = face_image.resize((128, 128))
                face_image = ImageOps.autocontrast(face_image)
                
                # Use simple hash method since imagehash might not be available
                img_bytes = face_image.tobytes()
                return hashlib.sha256(img_bytes).hexdigest()
            except Exception as e:
                print(f"    Face hash computation failed: {e}, falling back to full image")
        
        # Fall back to full image
        full_image = Image.open(image_path).convert("L")
        full_image = ImageOps.exif_transpose(full_image)
        full_image = full_image.resize((128, 128))
        full_image = ImageOps.autocontrast(full_image)
        img_bytes = full_image.tobytes()
        return hashlib.sha256(img_bytes).hexdigest()
        
    except Exception as e:
        print(f"    Hash computation error: {e}")
        # Fallback to basic file hash
        with open(image_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

def generate_augmented_encodings(image):
    """Generate multiple face encodings with slight augmentations for better recognition"""
    try:
        # Original encoding
        original_encodings = face_recognition.face_encodings(image)
        if not original_encodings:
            return []
            
        original_encoding = original_encodings[0]
        augmented_encodings = [original_encoding]
        
        # Convert to PIL for augmentations
        pil_image = Image.fromarray(image)
        
        # Slight brightness variations (+/- 10%)
        from PIL import ImageEnhance
        for factor in [0.9, 1.1]:
            try:
                enhancer = ImageEnhance.Brightness(pil_image)
                adjusted = enhancer.enhance(factor)
                adjusted_array = np.array(adjusted)
                adjusted_encodings = face_recognition.face_encodings(adjusted_array)
                if adjusted_encodings:
                    augmented_encodings.append(adjusted_encodings[0])
            except Exception as e:
                print(f"    Warning: brightness augmentation failed: {e}")
        
        # Small rotations (+/- 5 degrees)
        for angle in [-5, 5]:
            try:
                rotated = pil_image.rotate(angle)
                rotated_array = np.array(rotated)
                rotated_encodings = face_recognition.face_encodings(rotated_array)
                if rotated_encodings:
                    augmented_encodings.append(rotated_encodings[0])
            except Exception as e:
                print(f"    Warning: rotation augmentation failed: {e}")
        
        return augmented_encodings
        
    except Exception as e:
        print(f"    Error in augmentation: {e}")
        return []

def process_student_image(sample_image_path, student_id):
    """
    Process a sample image for a student:
    1. Copy to student_photos
    2. Extract face to face_only
    3. Generate augmented encodings
    4. Save encodings to face_encodings
    5. Compute hash
    
    Returns:
        tuple: (image_path, face_path, encoding_path, encoding_blob, image_hash, success)
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None, None, None, None, None, False
    
    try:
        # Create sanitized ID for filenames
        sanitized_id = student_id.replace('/', '_').replace('\\', '_')
        
        # Define paths
        student_image_path = os.path.join(STUDENT_PHOTOS_DIR, f"{sanitized_id}.jpg")
        face_image_path = os.path.join(FACE_ONLY_DIR, f"{sanitized_id}_face.jpg")
        encoding_path = os.path.join(FACE_ENCODINGS_DIR, f"student_{sanitized_id}_encodings.pkl")
        
        # Copy sample image to student_photos
        import shutil
        shutil.copy2(sample_image_path, student_image_path)
        
        # Extract face
        face_path = extract_face(student_image_path, face_image_path)
        
        if not face_path:
            print(f"    ⚠️  Face extraction failed for {student_id}")
            # Clean up
            if os.path.exists(student_image_path):
                os.remove(student_image_path)
            return None, None, None, None, None, False
        
        # Compute hash
        image_hash = compute_image_hash(student_image_path, face_image_path)
        
        # Load image for encoding
        image = face_recognition.load_image_file(student_image_path)
        
        # Generate augmented encodings
        augmented_encodings = generate_augmented_encodings(image)
        
        if not augmented_encodings:
            print(f"    ⚠️  No face encodings generated for {student_id}")
            # Clean up
            if os.path.exists(student_image_path):
                os.remove(student_image_path)
            if os.path.exists(face_image_path):
                os.remove(face_image_path)
            return None, None, None, None, None, False
        
        # Save encodings to file
        with open(encoding_path, 'wb') as f:
            pickle.dump(augmented_encodings, f)
        
        # Convert to blob for database (store first encoding)
        encoding_blob = pickle.dumps(augmented_encodings[0])
        
        return student_image_path, face_image_path, encoding_path, encoding_blob, image_hash, True
        
    except Exception as e:
        print(f"    ❌ Error processing image for {student_id}: {e}")
        return None, None, None, None, None, False

def generate_students_for_course(course_code, face_files, used_images):
    """Generate students for a specific course"""
    students = []
    course_info = COURSES[course_code]
    
    print(f"\n  Generating students for {course_code} - {course_info['name']}...")
    
    # Determine how many students per year (30-50 students per year)
    students_per_year_base = random.randint(30, 50)
    
    # Define admission cohorts
    admission_cohorts = [
        {"year": 2025, "study_year": 1, "semester": "1.2", "count": students_per_year_base},
        {"year": 2024, "study_year": 2, "semester": "2.2", "count": students_per_year_base},
        {"year": 2023, "study_year": 3, "semester": "3.2", "count": students_per_year_base},
        {"year": 2022, "study_year": 4, "semester": "4.2", "count": students_per_year_base},
        # Some retakes/deferred from previous years
        {"year": 2021, "study_year": 4, "semester": "4.2", "count": random.randint(3, 8)},
        {"year": 2021, "study_year": 3, "semester": "3.2", "count": random.randint(2, 5)},
        {"year": 2020, "study_year": 4, "semester": "4.2", "count": random.randint(1, 3)},
    ]
    
    for cohort in admission_cohorts:
        admission_year = cohort["year"]
        study_year = cohort["study_year"]
        semester = cohort["semester"]
        num_students = cohort["count"]
        
        print(f"    Year {study_year} (Admitted {admission_year}, /{admission_year % 100}): {num_students} students")
        
        successful_count = 0
        attempts = 0
        max_attempts = num_students * 3  # Allow multiple attempts if face detection fails
        
        # Generate students for this cohort
        for seq in range(1, num_students + 1):
            # Try to find an available image
            while attempts < max_attempts:
                attempts += 1
                
                # Get available images (not yet used)
                available_images = [img for img in face_files if img not in used_images]
                
                if not available_images:
                    print(f"      ⚠️  No more unused images available! Reusing images...")
                    available_images = face_files  # Allow reuse if we run out
                
                if not available_images:
                    print(f"      ❌ No face images available at all!")
                    break
                
                # Select random image
                sample_image_path = random.choice(available_images)
                
                # Generate student data
                student_id = generate_student_id(course_code, admission_year, seq)
                fname = random.choice(FIRST_NAMES)
                lname = random.choice(LAST_NAMES)
                email = get_email(f"{fname} {lname}")
                phone = generate_phone()
                
                # Process image
                image_path, face_path, encoding_path, encoding_blob, image_hash, success = \
                    process_student_image(sample_image_path, student_id)
                
                if success:
                    # Mark image as used
                    used_images.add(sample_image_path)
                    
                    # Create student
                    student = Student(
                        student_id=student_id,
                        fname=fname,
                        lname=lname,
                        email=email,
                        phone=phone,
                        course=course_code,
                        year_of_study=study_year,
                        current_semester=semester,
                        image_path=image_path,
                        image_hash=image_hash,
                        face_encoding=encoding_blob,
                        face_only_path=face_path,
                        face_encoding_path=encoding_path,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    # Set password (student_id)
                    student.set_password(student_id)
                    
                    students.append(student)
                    db.session.add(student)
                    successful_count += 1
                    
                    break  # Success, move to next student
                else:
                    # Try another image
                    print(f"      Retrying with different image... (attempt {attempts})")
                    continue
        
        print(f"      ✓ Successfully generated {successful_count}/{num_students} students")
    
    return students

def enroll_students_in_courses(students):
    """Enroll students in their respective courses"""
    print("\n📚 Enrolling Students in Courses...")
    
    enrollments = []
    
    for student in students:
        # Enroll in their main course
        enrollment = StudentCourse(
            student_id=student.student_id,
            course_code=student.course,
            semester=student.current_semester,
            year=student.year_of_study,
            enrollment_date=datetime.utcnow().date(),
            status='Active'
        )
        
        enrollments.append(enrollment)
        db.session.add(enrollment)
    
    db.session.commit()
    print(f"✅ {len(enrollments)} course enrollments created")
    return enrollments

def print_statistics(students):
    """Print generation statistics"""
    print("\n📊 Student Statistics:")
    print("-" * 70)
    
    total = len(students)
    with_faces = sum(1 for s in students if s.face_encoding is not None)
    
    print(f"Total Students: {total}")
    print(f"With Face Encodings: {with_faces} ({with_faces/total*100:.1f}%)")
    print(f"Without Face Encodings: {total - with_faces}")
    
    # By course
    print("\nBy Course:")
    for course_code in COURSES.keys():
        count = sum(1 for s in students if s.course == course_code)
        print(f"  {course_code}: {count} students")
    
    # By year
    print("\nBy Year of Study:")
    for year in range(1, 5):
        count = sum(1 for s in students if s.year_of_study == year)
        print(f"  Year {year}: {count} students")
    
    print("-" * 70)

def print_sample_students(students):
    """Print sample student data"""
    print("\n👤 Sample Students (First 10):")
    print("-" * 70)
    
    for student in students[:10]:
        face_status = "✓ With Face" if student.face_encoding else "✗ No Face"
        print(f"{student.student_id} | {student.fname} {student.lname:20} | {student.course} Y{student.year_of_study} | {face_status}")
    
    if len(students) > 10:
        print(f"... and {len(students) - 10} more")
    print("-" * 70)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT 3: STUDENTS WITH FACE ENCODINGS")
    print("=" * 70)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Verify prerequisites
            course_count = Course.query.count()
            
            if course_count == 0:
                print("\n❌ ERROR: Please run previous faker scripts first!")
                return
            
            print(f"\n✓ Found {course_count} courses")
            
            # Ensure directories exist
            ensure_directories()
            
            # Load face images
            face_files = load_sample_faces()
            
            if not face_files:
                print("\n❌ ERROR: No face images found!")
                print(f"   Please place face images (.jpg, .png) in: {SAMPLE_FACES_PATH}")
                return
            
            print(f"\n✓ Loaded {len(face_files)} sample face images")
            
            # Clear existing data
            clear_existing_data()
            
            # Track used images to avoid duplicates
            used_images = set()
            
            # Generate students for each course
            all_students = []
            
            for course_code in COURSES.keys():
                course_students = generate_students_for_course(course_code, face_files, used_images)
                all_students.extend(course_students)
                
                # Commit in batches to avoid memory issues
                if len(all_students) % 100 == 0:
                    db.session.commit()
                    print(f"\n  💾 Committed {len(all_students)} students so far...")
            
            # Final commit
            db.session.commit()
            print(f"\n✅ {len(all_students)} students created")
            
            # Enroll in courses
            enrollments = enroll_students_in_courses(all_students)
            
            # Statistics
            print_statistics(all_students)
            print_sample_students(all_students)
            
            # Summary
            print("\n" + "=" * 70)
            print("✅ DATA GENERATION COMPLETE!")
            print("=" * 70)
            print(f"👥 Students: {len(all_students)}")
            print(f"📚 Enrollments: {len(enrollments)}")
            print(f"📸 With Face Encodings: {sum(1 for s in all_students if s.face_encoding)}")
            print(f"🖼️  Unique Images Used: {len(used_images)} / {len(face_files)}")
            print("\n🔐 STUDENT LOGIN CREDENTIALS:")
            print("   Username: Student ID (e.g., S13-2024-001)")
            print("   Password: Student ID (same as username)")
            print("\n📂 IMAGE LOCATIONS:")
            print(f"   Student Photos: {STUDENT_PHOTOS_DIR}")
            print(f"   Face Only: {FACE_ONLY_DIR}")
            print(f"   Encodings: {FACE_ENCODINGS_DIR}")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()