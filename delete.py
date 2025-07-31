#!/usr/bin/env python3
import os
import sys
import random
import sqlite3
import shutil
import pickle
import argparse
from PIL import Image, ImageOps
import face_recognition
import imagehash
import re
import numpy as np
from faker import Faker
import glob

# Constants matching your system
IMAGE_DIR = "student_images"
ENCODING_DIR = "face_encodings"  # This seems to be your encodings directory based on the code
SAMPLE_FACES_DIR = "sample_faces"  # Directory with thispersondoesnotexist images

# Ensure directories exist
for directory in [IMAGE_DIR, ENCODING_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Initialize faker
fake = Faker()

def setup_argument_parser():
    """Set up command line argument parsing"""
    parser = argparse.ArgumentParser(description='Generate fake student data for testing')
    parser.add_argument('-n', '--number', type=int, default=480, 
                        help='Number of fake students to generate (default: 10)')
    parser.add_argument('-d', '--database', default='attendance.db',
                        help='Path to SQLite database file (default: attendance.db)')
    parser.add_argument('--reset', action='store_true',
                        help='Remove all generated students before adding new ones')
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')
    return parser.parse_args()

def get_course_codes(db_conn):
    """Get list of valid course codes from database"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT course_code FROM courses")
    return [row[0] for row in cursor.fetchall()]

def generate_student_id(course_code, year_of_study):
    """Generate a student ID in the format S00/00000/YY with appropriate registration year"""
    import datetime
    
    # Current year (last two digits)
    current_year = datetime.datetime.now().year % 100
    
    # Calculate registration year based on desired year of study
    # For year 1: current year
    # For year 2: current year - 1
    # For year 3: current year - 2
    # For year 4: current year - 3
    reg_year = current_year - (year_of_study - 1)
    
    # Ensure reg_year is between 17 and 25
    if reg_year < 17:
        reg_year = 17
    elif reg_year > 25:
        reg_year = 25
    
    serial = random.randint(10000, 99999)  # 5-digit serial number
    
    return f"{course_code}/{serial}/{reg_year:02d}"

def determine_current_semester(year_of_study, student_id):
    """Determine current semester based on current date and student's year"""
    import datetime
    
    today = datetime.date.today()
    month = today.month
    
    # Extract registration year from ID
    reg_year = None
    match = re.match(r"^S\d{2}/\d{5}/(\d{2})$", student_id)
    if match:
        reg_year = int(match.group(1))
    
    # Determine base semester from month
    if 9 <= month <= 12:
        # First semester (September to December)
        base_semester = 1
    elif 1 <= month <= 4:
        # Second semester (January to April)
        base_semester = 2
    else:
        # Default to first semester during break months
        base_semester = 1
    
    # Special adjustments for specific cohorts
    if reg_year == 24:  # 2024 cohort
        # Currently in second semester of first year
        if year_of_study == 1:
            return 2
    
    return base_semester

def compute_phash(image_path, face_only_path=None):
    """Compute perceptual hash prioritizing face if available"""
    try:
        # If face extraction succeeded, use that for hashing
        if face_only_path and os.path.exists(face_only_path):
            try:
                # Process face image
                face_image = Image.open(face_only_path).convert("L")
                face_image = ImageOps.exif_transpose(face_image)
                face_image = face_image.resize((128, 128))
                face_image = ImageOps.autocontrast(face_image)
                return str(imagehash.phash(face_image)), True  # Return with flag indicating face was used
            except Exception as e:
                print(f"Face hash computation failed: {e}, falling back to full image")
        
        # Fall back to full image if face extraction failed or caused an error
        full_image = Image.open(image_path).convert("L")
        full_image = ImageOps.exif_transpose(full_image)
        full_image = full_image.resize((128, 128))
        full_image = ImageOps.autocontrast(full_image)
        return str(imagehash.phash(full_image)), False  # Return with flag indicating full image was used
        
    except Exception as e:
        print(f"Hash computation error: {e}")
        return None, False

def extract_face(image_path, face_output_path):
    """Extract face from image and save to separate file"""
    try:
        # Load the image
        image = face_recognition.load_image_file(image_path)
        
        # Find face locations
        face_locations = face_recognition.face_locations(image)
        
        if not face_locations:
            print(f"No face found in {image_path}")
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
        import cv2
        cv2.imwrite(face_output_path, face_img)
        
        return face_output_path
        
    except Exception as e:
        print(f"Error extracting face: {e}")
        return None

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
        for factor in [0.9, 1.1]:
            try:
                # Apply brightness adjustment
                enhancer = ImageOps.autocontrast(pil_image)
                # Convert back to numpy array
                adjusted = np.array(enhancer)
                # Get encodings from the adjusted image
                adjusted_encodings = face_recognition.face_encodings(adjusted)
                if adjusted_encodings:
                    augmented_encodings.append(adjusted_encodings[0])
            except Exception as e:
                print(f"Error generating brightness augmentation: {e}")
        
        # Small rotations (+/- 5 degrees)
        for angle in [-5, 5]:
            try:
                # Apply rotation
                rotated = pil_image.rotate(angle)
                # Convert back to numpy array
                rotated_array = np.array(rotated)
                # Get encodings from the rotated image
                rotated_encodings = face_recognition.face_encodings(rotated_array)
                if rotated_encodings:
                    augmented_encodings.append(rotated_encodings[0])
            except Exception as e:
                print(f"Error generating rotation augmentation: {e}")
        
        return augmented_encodings
        
    except Exception as e:
        print(f"Error in augmentation: {e}")
        return []

def get_available_images(used_images):
    """Get list of available sample face images that haven't been used"""
    all_images = glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.jpg"))
    all_images.extend(glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.png")))
    
    # Filter out already used images
    available_images = [img for img in all_images if img not in used_images]
    
    if not available_images:
        print("Warning: All sample images have been used. Will start reusing images.")
        return all_images
    
    return available_images

def is_duplicate_hash(db_conn, image_hash):
    """Check if the hash already exists in the database"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students WHERE image_hash = ?", (image_hash,))
    count = cursor.fetchone()[0]
    return count > 0

def clear_generated_students(db_conn):
    """Remove all previously generated students (optional)"""
    try:
        cursor = db_conn.cursor()
        
        # First get list of students to delete
        cursor.execute("SELECT student_id, image_path, face_only_path, face_encoding_path FROM students")
        students = cursor.fetchall()
        
        # Delete related records from student_courses
        cursor.execute("DELETE FROM student_courses")
        
        # Delete from attendance
        cursor.execute("DELETE FROM attendance")
        
        # Delete from students
        cursor.execute("DELETE FROM students")

        db_conn.commit()
        
        # Delete files
        for student_id, image_path, face_path, encoding_path in students:
            try:
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                if face_path and os.path.exists(face_path):
                    os.remove(face_path)
                if encoding_path and os.path.exists(encoding_path):
                    os.remove(encoding_path)
            except Exception as e:
                print(f"Error removing files for student {student_id}: {e}")
        
        print("All generated students removed from database and file system")
        
    except sqlite3.Error as e:
        print(f"Database error while clearing students: {e}")
    except Exception as e:
        print(f"Error clearing students: {e}")

def get_existing_student_ids(db_conn):
    """Get list of existing student IDs to avoid duplicates"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT student_id FROM students")
    return [row[0] for row in cursor.fetchall()]

def generate_fake_students(db_conn, num_students):
    """Generate fake student entries with unique images"""
    try:
        cursor = db_conn.cursor()
        
        # Get course codes from database
        course_codes = get_course_codes(db_conn)
        if not course_codes:
            print("Error: No courses found in database")
            return
            
        # Get existing student IDs to avoid duplicates
        existing_student_ids = get_existing_student_ids(db_conn)
        
        # Track already used images to avoid duplicates
        used_images = []
        
        # Track success
        success_count = 0
        
        # Calculate how many students to assign to each year
        students_per_year = num_students // 4
        remaining = num_students % 4
        
        # Distribution of students by year
        year_distribution = [students_per_year] * 4
        
        # Add remaining students to years starting from year 1
        for i in range(remaining):
            year_distribution[i] += 1
            
        print(f"Student distribution by year: Year 1: {year_distribution[0]}, Year 2: {year_distribution[1]}, Year 3: {year_distribution[2]}, Year 4: {year_distribution[3]}")
        
        # Generate students for each year
        current_student = 0
        
        for year_of_study in range(1, 5):
            students_for_this_year = year_distribution[year_of_study-1]
            
            print(f"Generating {students_for_this_year} students for Year {year_of_study}...")
            
            for i in range(students_for_this_year):
                try:
                    current_student += 1
                    print(f"Generating student {current_student}/{num_students} (Year {year_of_study})...")
                    
                    # Get random image that hasn't been used
                    available_images = get_available_images(used_images)
                    if not available_images:
                        print("Error: No available sample face images found")
                        break
                        
                    sample_image_path = random.choice(available_images)
                    used_images.append(sample_image_path)
                    
                    # Generate basic info - split name into fname and lname
                    full_name = fake.name()
                    name_parts = full_name.split()
                    
                    # Handle different name formats
                    if len(name_parts) >= 2:
                        fname = name_parts[0]
                        lname = " ".join(name_parts[1:])
                    else:
                        fname = name_parts[0]
                        lname = ""
                    
                    # Select random course
                    course_code = random.choice(course_codes)
                    
                    # Generate unique student ID based on assigned year of study
                    while True:
                        student_id = generate_student_id(course_code, year_of_study)
                        if student_id not in existing_student_ids:
                            existing_student_ids.append(student_id)
                            break
                    
                    # Determine appropriate semester
                    semester_num = determine_current_semester(year_of_study, student_id)
                    
                    # Format semester string (e.g. "2.1")
                    semester = f"{year_of_study}.{semester_num}"
                    
                    # Create sanitized ID for filenames
                    sanitized_id = student_id.replace('/', '_')
                    
                    # Prepare image file paths
                    final_image_path = os.path.join(IMAGE_DIR, f"{sanitized_id}.jpg")
                    face_image_path = os.path.join(IMAGE_DIR, f"{sanitized_id}_face.jpg")
                    encoding_path = os.path.join(ENCODING_DIR, f"student_{sanitized_id}_encodings.pkl")
                    
                    # Copy and process sample image
                    shutil.copy2(sample_image_path, final_image_path)
                    
                    # Extract face
                    extract_face(final_image_path, face_image_path)
                    
                    # Compute hash
                    image_hash, used_face = compute_phash(final_image_path, face_image_path)
                    
                    # Check for duplicate hash
                    if is_duplicate_hash(db_conn, image_hash):
                        print(f"Duplicate hash detected for {student_id}. Skipping...")
                        # Clean up files
                        if os.path.exists(final_image_path):
                            os.remove(final_image_path)
                        if os.path.exists(face_image_path):
                            os.remove(face_image_path)
                        continue
                    
                    # Generate face encodings
                    image = face_recognition.load_image_file(final_image_path)
                    augmented_encodings = generate_augmented_encodings(image)
                    
                    if not augmented_encodings:
                        print(f"No face detected in {final_image_path}. Skipping...")
                        continue
                    
                    # Save encodings to file
                    with open(encoding_path, 'wb') as f:
                        pickle.dump(augmented_encodings, f)
                        
                    # Convert to blob for database
                    encoding_blob = pickle.dumps(augmented_encodings)
                    
                    # Generate additional details
                    email = fake.email()
                    phone = f"07{random.randint(10000000, 99999999)}"  # Format: 07XXXXXXXX
                    
                    # Insert student into database
                    cursor.execute("""
                        INSERT INTO students (
                            fname, lname, student_id, image_path, image_hash, face_encoding, 
                            face_only_path, course, year_of_study, email, phone, 
                            current_semester, face_encoding_path
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        fname, lname, student_id, final_image_path, image_hash, encoding_blob, 
                        face_image_path, course_code, year_of_study, email, phone, 
                        semester, encoding_path
                    ))
                    
                    # Insert student course enrollment
                    cursor.execute("""
                        INSERT INTO student_courses 
                        (student_id, course_code, semester, enrollment_date)
                        VALUES (?, ?, ?, date('now'))
                    """, (student_id, course_code, semester))
                    
                    # Log activity
                    cursor.execute("""
                        INSERT INTO activity_log 
                        (user_id, activity_type, timestamp)
                        VALUES (?, ?, datetime('now', 'localtime'))
                    """, ("faker_script", f"Student registered: {student_id}"))
                    
                    db_conn.commit()
                    success_count += 1
                    print(f"Successfully created student: {fname} {lname} ({student_id}) - Year {year_of_study}, Semester {semester}")
                    
                except Exception as e:
                    print(f"Error generating student {current_student}: {e}")
                    db_conn.rollback()
                    
        print(f"Generation complete. Successfully created {success_count} out of {num_students} students.")
        print(f"Year distribution of created students:")
        for year in range(1, 5):
            cursor.execute("SELECT COUNT(*) FROM students WHERE year_of_study = ?", (year,))
            count = cursor.fetchone()[0]
            print(f"Year {year}: {count} students")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    args = setup_argument_parser()
    
    # Set random seed if provided
    if args.seed:
        random.seed(args.seed)
        fake.seed_instance(args.seed)
    
    # Check if the sample faces directory exists
    if not os.path.exists(SAMPLE_FACES_DIR):
        print(f"Error: Sample faces directory '{SAMPLE_FACES_DIR}' not found.")
        print("Please create this directory and add sample face images before running this script.")
        return 1
    
    # Count available sample images
    sample_images = glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.jpg"))
    sample_images.extend(glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.png")))
    
    if not sample_images:
        print(f"Error: No sample face images found in '{SAMPLE_FACES_DIR}'.")
        print("Please add .jpg or .png images to this directory before running this script.")
        return 1
    
    print(f"Found {len(sample_images)} sample face images.")
    
    try:
        # Connect to database
        conn = sqlite3.connect(args.database)
        
        # Reset if requested
        if args.reset:
            print("Removing all previously generated students...")
            clear_generated_students(conn)
        
        # Generate fake students
        print(f"Generating {args.number} fake students...")
        generate_fake_students(conn, args.number)
        
        conn.close()
        return 0
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())