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
import glob

# Constants matching your system
IMAGE_DIR = "student_images"
ENCODING_DIR = "face_encodings"
SAMPLE_FACES_DIR = "sample_faces"

# Ensure directories exist
for directory in [IMAGE_DIR, ENCODING_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Kenyan Christian names (expanded)
KENYAN_FIRST_NAMES_MALE = [
    "Joseph", "John", "David", "Peter", "James", "Daniel", "Samuel", "Michael",
    "Stephen", "Paul", "Mark", "Luke", "Matthew", "Simon", "Thomas", "Andrew",
    "Philip", "Timothy", "Benjamin", "Emmanuel", "Joshua", "Isaac", "Jacob",
    "Moses", "Elijah", "Nathan", "Solomon", "Caleb", "Abel", "Seth", "Noah",
    "Brian", "Kevin", "Ian", "Eric", "Dennis", "Victor", "Felix", "Collins",
    "Martin", "Francis", "Patrick", "Anthony", "Vincent", "Leonard", "Gilbert",
    "Robert", "William", "Richard", "Charles", "George", "Edward", "Henry",
    "Geoffrey", "Kenneth", "Ronald", "Donald", "Raymond", "Albert", "Fred",
    "Alex", "Chris", "Nicholas", "Lawrence", "Boniface", "Augustine", "Edwin"
]

KENYAN_FIRST_NAMES_FEMALE = [
    "Mary", "Grace", "Faith", "Ruth", "Sarah", "Hannah", "Esther", "Rebecca",
    "Rachel", "Elizabeth", "Martha", "Deborah", "Judith", "Eve", "Naomi",
    "Miriam", "Anna", "Joy", "Hope", "Mercy", "Charity", "Patience", "Lydia",
    "Priscilla", "Eunice", "Dorcas", "Sharon", "Rose", "Catherine", "Margaret",
    "Jane", "Lucy", "Ann", "Christine", "Joyce", "Nancy", "Betty", "Susan",
    "Agnes", "Winnie", "Purity", "Blessing", "Gloria", "Jennifer", "Michelle",
    "Patricia", "Linda", "Barbara", "Carol", "Helen", "Dorothy", "Alice",
    "Irene", "Florence", "Beatrice", "Veronica", "Monica", "Caroline", "Diana"
]

KENYAN_LAST_NAMES = [
    "Kamau", "Njoroge", "Wanjiru", "Mwangi", "Ochieng", "Otieno", "Kipchoge",
    "Kimani", "Kariuki", "Wambui", "Gitau", "Njeri", "Mutua", "Maina", "Kibet",
    "Wanyama", "Onyango", "Wekesa", "Muthoni", "Nyambura", "Njuguna", "Gathoni",
    "Kiptoo", "Koech", "Rotich", "Cheruiyot", "Biwott", "Kiplagat", "Chepkwony",
    "Jepkorir", "Achieng", "Awiti", "Adhiambo", "Akoth", "Atieno", "Nekesa",
    "Nafula", "Andika", "Omondi", "Ogola", "Mulei", "Musyoka", "Mueni", "Ndunge",
    "Wairimu", "Wangari", "Gachanja", "Mugo", "Waititu", "Karanja", "Kiprono",
    "Njihia", "Kuria", "Mbugua", "Macharia", "Thuo", "Ndirangu", "Kabiru",
    "Njenga", "Ndegwa", "Kinyanjui", "Ngugi", "Waweru", "Githinji", "Mwenda"
]

def generate_kenyan_name():
    """Generate a random Kenyan Christian name"""
    gender = random.choice(['male', 'female'])
    
    if gender == 'male':
        first_name = random.choice(KENYAN_FIRST_NAMES_MALE)
    else:
        first_name = random.choice(KENYAN_FIRST_NAMES_FEMALE)
    
    last_name = random.choice(KENYAN_LAST_NAMES)
    
    return first_name, last_name

def generate_kenyan_phone():
    """Generate a realistic Kenyan phone number"""
    prefixes = ['0710', '0711', '0712', '0720', '0721', '0722', '0723', '0724',
                '0725', '0726', '0727', '0728', '0729', '0740', '0741', '0742',
                '0743', '0745', '0746', '0748', '0757', '0758', '0759', '0768',
                '0769', '0790', '0791', '0792', '0793', '0794', '0795', '0796',
                '0797', '0798', '0799']
    
    prefix = random.choice(prefixes)
    suffix = random.randint(100000, 999999)
    return f"{prefix}{suffix}"

def generate_kenyan_email(first_name, last_name, student_id):
    """Generate a realistic Kenyan email"""
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'student.edu.ke']
    
    # Extract year from student ID
    match = re.match(r"^[A-Z]+/\d{5}/(\d{2})$", student_id)
    year_suffix = match.group(1) if match else str(random.randint(20, 25))
    
    email_formats = [
        f"{first_name.lower()}.{last_name.lower()}@{random.choice(domains)}",
        f"{first_name.lower()}{last_name.lower()}@{random.choice(domains)}",
        f"{first_name.lower()}.{last_name.lower()}{year_suffix}@{random.choice(domains)}",
        f"{first_name[0].lower()}{last_name.lower()}@{random.choice(domains)}"
    ]
    
    return random.choice(email_formats)

def setup_argument_parser():
    """Set up command line argument parsing"""
    parser = argparse.ArgumentParser(description='Generate fake student data for testing')
    parser.add_argument('-n', '--number', type=int, default=450, 
                        help='Number of fake students to generate (default: 450)')
    parser.add_argument('-d', '--database', default='attendance.db',
                        help='Path to SQLite database file (default: attendance.db)')
    parser.add_argument('--reset', action='store_true',
                        help='Remove all generated students before adding new ones')
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')
    return parser.parse_args()

def get_courses_with_info(db_conn):
    """Get list of valid courses with their details"""
    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT course_code, course_name, faculty 
        FROM courses 
        WHERE is_active = 1
        ORDER BY course_code
    """)
    return cursor.fetchall()

def get_classes_for_course_year(db_conn, course_code, year):
    """Get all classes for a specific course and year in current semester"""
    cursor = db_conn.cursor()
    current_semester_num = get_current_academic_semester()
    
    # FIXED: Query using separate year and semester INTEGER columns
    cursor.execute("""
        SELECT c.class_id, c.class_name, c.semester
        FROM classes c
        WHERE c.course_code = ?
        AND c.year = ?
        AND c.semester = ?
        AND c.is_active = 1
        ORDER BY c.class_id
    """, (course_code, year, current_semester_num))
    
    return cursor.fetchall()
    
def generate_student_id(course_code, year_of_study):
    """Generate a student ID in the format COURSE/00000/YY with appropriate registration year"""
    import datetime
    
    current_year = datetime.datetime.now().year % 100
    reg_year = current_year - (year_of_study - 1)
    
    if reg_year < 17:
        reg_year = 17
    elif reg_year > 25:
        reg_year = 25
    
    serial = random.randint(10000, 99999)
    
    return f"{course_code}/{serial}/{reg_year:02d}"

def get_current_academic_semester():
    """
    Determine current academic semester based on current date.
    Returns semester number (1 or 2) that ALL students in campus are currently in.
    
    Academic Calendar:
    - Semester 1: September to December
    - Semester 2: January to April
    - Break: May to August (defaults to Semester 1 preparation)
    """
    import datetime
    
    today = datetime.date.today()
    month = today.month
    
    if 9 <= month <= 12:
        return 1
    elif 1 <= month <= 4:
        return 2
    else:
        return 1

def determine_student_semester(year_of_study):
    """
    Determine a student's current semester based on their year of study
    and the current academic semester.
    
    Format: "YEAR.SEMESTER" (e.g., "2.1" means Year 2, Semester 1)
    """
    current_semester = get_current_academic_semester()
    return f"{year_of_study}.{current_semester}"

def compute_phash(image_path, face_only_path=None):
    """Compute perceptual hash prioritizing face if available"""
    try:
        if face_only_path and os.path.exists(face_only_path):
            try:
                face_image = Image.open(face_only_path).convert("L")
                face_image = ImageOps.exif_transpose(face_image)
                face_image = face_image.resize((128, 128))
                face_image = ImageOps.autocontrast(face_image)
                return str(imagehash.phash(face_image)), True
            except Exception as e:
                print(f"Face hash computation failed: {e}, falling back to full image")
        
        full_image = Image.open(image_path).convert("L")
        full_image = ImageOps.exif_transpose(full_image)
        full_image = full_image.resize((128, 128))
        full_image = ImageOps.autocontrast(full_image)
        return str(imagehash.phash(full_image)), False
        
    except Exception as e:
        print(f"Hash computation error: {e}")
        return None, False

def extract_face(image_path, face_output_path):
    """Extract face from image and save to separate file"""
    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)
        
        if not face_locations:
            print(f"No face found in {image_path}")
            return None
            
        top, right, bottom, left = face_locations[0]
        
        face_width = right - left
        face_height = bottom - top
        pad_x = int(0.2 * face_width)
        pad_y = int(0.2 * face_height)
        
        left = max(0, left - pad_x)
        top = max(0, top - pad_y)
        right = min(image.shape[1], right + pad_x)
        bottom = min(image.shape[0], bottom + pad_y)
        
        face_img = image[top:bottom, left:right]
        face_pil = Image.fromarray(face_img)
        face_pil.save(face_output_path)
        
        return face_output_path
        
    except Exception as e:
        print(f"Error extracting face: {e}")
        return None

def generate_augmented_encodings(image):
    """Generate multiple face encodings with slight augmentations for better recognition"""
    try:
        original_encodings = face_recognition.face_encodings(image)
        if not original_encodings:
            return []
            
        original_encoding = original_encodings[0]
        augmented_encodings = [original_encoding]
        
        pil_image = Image.fromarray(image)
        
        for _ in [0.9, 1.1]:
            try:
                enhancer = ImageOps.autocontrast(pil_image)
                adjusted = np.array(enhancer)
                adjusted_encodings = face_recognition.face_encodings(adjusted)
                if adjusted_encodings:
                    augmented_encodings.append(adjusted_encodings[0])
            except Exception:
                pass
        
        for angle in [-5, 5]:
            try:
                rotated = pil_image.rotate(angle)
                rotated_array = np.array(rotated)
                rotated_encodings = face_recognition.face_encodings(rotated_array)
                if rotated_encodings:
                    augmented_encodings.append(rotated_encodings[0])
            except Exception:
                pass
        
        return augmented_encodings
        
    except Exception as e:
        print(f"Error in augmentation: {e}")
        return []

def get_available_images(used_images):
    """Get list of available sample face images that haven't been used"""
    all_images = glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.jpg"))
    all_images.extend(glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.png")))
    
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
    """Remove all previously generated students"""
    try:
        cursor = db_conn.cursor()
        
        cursor.execute("SELECT student_id, image_path, face_only_path, face_encoding_path FROM students")
        students = cursor.fetchall()
        
        cursor.execute("DELETE FROM student_courses")
        cursor.execute("DELETE FROM class_enrollments")
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM students")
        db_conn.commit()
        
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
        
        print("✓ All generated students removed from database and file system")
        
    except sqlite3.Error as e:
        print(f"Database error while clearing students: {e}")
    except Exception as e:
        print(f"Error clearing students: {e}")

def get_existing_student_ids(db_conn):
    """Get list of existing student IDs to avoid duplicates"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT student_id FROM students")
    return [row[0] for row in cursor.fetchall()]

def calculate_course_year_distribution(total_students, courses, years=[1, 2, 3, 4]):
    """
    Calculate realistic and balanced student distribution across courses and years.
    
    Distribution strategy:
    - Year 1: 35% (largest intake)
    - Year 2: 30% (some attrition)
    - Year 3: 22% (more attrition)
    - Year 4: 13% (final year, smallest)
    - Courses distributed more evenly with controlled variation
    """
    year_distribution = {
        1: 0.35,  # 35% first years
        2: 0.30,  # 30% second years
        3: 0.22,  # 22% third years
        4: 0.13   # 13% fourth years
    }
    
    num_courses = len(courses)
    distribution = {}
    
    # First, calculate base students per course (equal distribution)
    base_per_course = total_students // num_courses
    remainder = total_students % num_courses
    
    # Assign base amounts to each course with slight variations
    course_totals = {}
    for i, course in enumerate(courses):
        course_code = course[0]
        # Add variation: some courses ±15% from base
        variation = random.uniform(0.85, 1.15)
        course_total = int(base_per_course * variation)
        
        # Ensure minimum viable course size (at least 40 students)
        course_total = max(40, course_total)
        course_totals[course_code] = course_total
    
    # Normalize to match total_students exactly
    current_total = sum(course_totals.values())
    if current_total != total_students:
        # Adjust proportionally
        adjustment_factor = total_students / current_total
        for course_code in course_totals:
            course_totals[course_code] = int(course_totals[course_code] * adjustment_factor)
    
    # Distribute any remaining students to random courses
    current_total = sum(course_totals.values())
    remaining_to_distribute = total_students - current_total
    
    if remaining_to_distribute > 0:
        random_courses = random.sample(list(course_totals.keys()), 
                                      min(remaining_to_distribute, len(course_totals)))
        for course_code in random_courses:
            course_totals[course_code] += 1
    elif remaining_to_distribute < 0:
        # Remove excess from courses with most students
        sorted_courses = sorted(course_totals.items(), key=lambda x: x[1], reverse=True)
        for i in range(abs(remaining_to_distribute)):
            course_code = sorted_courses[i % len(sorted_courses)][0]
            if course_totals[course_code] > 40:  # Don't go below minimum
                course_totals[course_code] -= 1
    
    # Now distribute each course's students across years
    for course_code, course_total in course_totals.items():
        distribution[course_code] = {}
        remaining = course_total
        
        for year in sorted(years):
            if year == max(years):
                # Last year gets remaining
                distribution[course_code][year] = max(3, remaining)
            else:
                # Calculate based on year distribution percentages
                year_count = int(course_total * year_distribution[year])
                # Ensure minimum per year (at least 3 students)
                year_count = max(3, year_count)
                # Don't exceed remaining
                year_count = min(year_count, remaining - (len(years) - years.index(year)) * 3)
                distribution[course_code][year] = year_count
                remaining -= year_count
    
    return distribution

def enroll_student_in_classes(db_conn, student_id, course_code, year):
    """Enroll student in all classes for their course, year, and current semester"""
    cursor = db_conn.cursor()
    current_semester = get_current_academic_semester()
    
    # Get all classes for this course, year, and semester
    cursor.execute("""
        SELECT class_id
        FROM classes
        WHERE course_code = ?
        AND year_level = ?
        AND semester = ?
        AND is_active = 1
    """, (course_code, year, current_semester))
    
    classes = cursor.fetchall()
    
    # Enroll in each class
    for (class_id,) in classes:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO class_enrollments
                (student_id, class_id, semester, academic_year, status)
                VALUES (?, ?, ?, '2025/2026', 'active')
            """, (student_id, class_id, current_semester))
        except sqlite3.Error as e:
            print(f"    Warning: Could not enroll in {class_id}: {e}")
    
    db_conn.commit()
    return len(classes)

def generate_fake_students(db_conn, num_students):
    """Generate fake student entries organized by course and year"""
    try:
        cursor = db_conn.cursor()
        
        courses = get_courses_with_info(db_conn)
        if not courses:
            print("Error: No courses found in database")
            return
        
        # Calculate distribution across courses and years
        distribution = calculate_course_year_distribution(num_students, courses)
        
        existing_student_ids = get_existing_student_ids(db_conn)
        used_images = []
        success_count = 0
        
        current_semester_num = get_current_academic_semester()
        semester_name = "Semester 1" if current_semester_num == 1 else "Semester 2"
        
        print(f"\nCurrent Academic Period: {semester_name}")
        print(f"\n{'='*70}")
        print(f"STUDENT DISTRIBUTION PLAN")
        print(f"{'='*70}")
        
        # Display distribution
        total_planned = 0
        for course_code, course_name, faculty in courses:
            if course_code in distribution:
                course_total = sum(distribution[course_code].values())
                total_planned += course_total
                print(f"\n{course_name} ({course_code}):")
                for year in sorted(distribution[course_code].keys()):
                    count = distribution[course_code][year]
                    print(f"  Year {year}: {count} students")
        
        print(f"\n{'='*70}")
        print(f"Total students to generate: {total_planned}")
        print(f"{'='*70}\n")
        
        # Generate students by course and year
        for course_code, course_name, faculty in courses:
            if course_code not in distribution:
                continue
            
            print(f"\n>>> Processing {course_name} ({course_code})...")
            
            for year in sorted(distribution[course_code].keys()):
                num_for_year = distribution[course_code][year]
                
                # Get classes for this course/year combination
                classes = get_classes_for_course_year(db_conn, course_code, year)
                
                if not classes:
                    print(f"  Warning: No classes found for {course_code} Year {year} in {semester_name}.")
                    print(f"  Students will still be created but won't be enrolled in classes.")
                
                if classes:
                    print(f"\n  Generating {num_for_year} students for Year {year}...")
                    print(f"  These students will be enrolled in {len(classes)} classes:")
                    for class_id, class_name, _ in classes:
                        print(f"    - {class_name} ({class_id})")
                else:
                    print(f"\n  Generating {num_for_year} students for Year {year} (no class enrollment)...")
                
                for i in range(num_for_year):
                    try:
                        success_count += 1
                        print(f"\n  [{success_count}/{total_planned}] Creating student...")
                        
                        available_images = get_available_images(used_images)
                        if not available_images:
                            print("    Error: No available sample face images")
                            success_count -= 1
                            break
                        
                        sample_image_path = random.choice(available_images)
                        used_images.append(sample_image_path)
                        
                        # Generate Kenyan name
                        fname, lname = generate_kenyan_name()
                        
                        # Generate unique student ID
                        while True:
                            student_id = generate_student_id(course_code, year)
                            if student_id not in existing_student_ids:
                                existing_student_ids.append(student_id)
                                break
                        
                        semester = determine_student_semester(year)
                        sanitized_id = student_id.replace('/', '_')
                        
                        final_image_path = os.path.join(IMAGE_DIR, f"{sanitized_id}.jpg")
                        face_image_path = os.path.join(IMAGE_DIR, f"{sanitized_id}_face.jpg")
                        encoding_path = os.path.join(ENCODING_DIR, f"student_{sanitized_id}_encodings.pkl")
                        
                        shutil.copy2(sample_image_path, final_image_path)
                        extract_face(final_image_path, face_image_path)
                        
                        image_hash, _ = compute_phash(final_image_path, face_image_path)
                        
                        if is_duplicate_hash(db_conn, image_hash):
                            print(f"    Duplicate hash detected. Skipping...")
                            if os.path.exists(final_image_path):
                                os.remove(final_image_path)
                            if os.path.exists(face_image_path):
                                os.remove(face_image_path)
                            success_count -= 1
                            continue
                        
                        image = face_recognition.load_image_file(final_image_path)
                        augmented_encodings = generate_augmented_encodings(image)
                        
                        if not augmented_encodings:
                            print(f"    No face detected. Skipping...")
                            success_count -= 1
                            continue
                        
                        with open(encoding_path, 'wb') as f:
                            pickle.dump(augmented_encodings, f)
                        
                        encoding_blob = pickle.dumps(augmented_encodings)
                        
                        email = generate_kenyan_email(fname, lname, student_id)
                        phone = generate_kenyan_phone()
                        
                        # Insert student
                        cursor.execute("""
                            INSERT INTO students (
                                fname, lname, student_id, image_path, image_hash, face_encoding, 
                                face_only_path, course, year_of_study, email, phone, 
                                current_semester, face_encoding_path, password, is_active
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fname, lname, student_id, final_image_path, image_hash, encoding_blob, 
                            face_image_path, course_code, year, email, phone, 
                            semester, encoding_path, "password123", 1
                        ))
                        
                        # Enroll in course
                        cursor.execute("""
                            INSERT INTO student_courses 
                            (student_id, course_code, semester, year, enrollment_date, status)
                            VALUES (?, ?, ?, ?, date('now'), ?)
                        """, (student_id, course_code, semester, year, 'Active'))
                        
                        # Enroll in classes
                        num_classes = enroll_student_in_classes(db_conn, student_id, course_code, year)
                        
                        # Log activity
                        cursor.execute("""
                            INSERT INTO activity_log 
                            (user_id, user_type, activity_type, description, timestamp)
                            VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
                        """, ("generator_script", "admin", "student_registration", 
                             f"Student registered: {student_id} - {fname} {lname}"))
                        
                        db_conn.commit()
                        enrollment_info = f"enrolled in {num_classes} classes" if num_classes > 0 else "no class enrollment"
                        print(f"    ✓ {fname} {lname} ({student_id}) - Year {year}, {course_name} ({enrollment_info})")
                        
                    except Exception as e:
                        print(f"    Error generating student: {e}")
                        db_conn.rollback()
                        success_count -= 1
        
        print(f"\n{'='*70}")
        print(f"GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"Successfully created {success_count} students")
        
        # Show final statistics
        print(f"\n{'='*70}")
        print("FINAL STATISTICS")
        print(f"{'='*70}")
        
        for course_code, course_name, _ in courses:
            cursor.execute("""
                SELECT year_of_study, COUNT(*) 
                FROM students 
                WHERE course = ? 
                GROUP BY year_of_study 
                ORDER BY year_of_study
            """, (course_code,))
            results = cursor.fetchall()
            
            if results:
                print(f"\n{course_name} ({course_code}):")
                total = 0
                for year, count in results:
                    print(f"  Year {year}: {count} students")
                    total += count
                print(f"  Total: {total} students")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    args = setup_argument_parser()
    
    if args.seed:
        random.seed(args.seed)
    
    if not os.path.exists(SAMPLE_FACES_DIR):
        print(f"Error: Sample faces directory '{SAMPLE_FACES_DIR}' not found.")
        print("Please create this directory and add sample face images before running this script.")
        return 1
    
    sample_images = glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.jpg"))
    sample_images.extend(glob.glob(os.path.join(SAMPLE_FACES_DIR, "*.png")))
    
    if not sample_images:
        print(f"Error: No sample face images found in '{SAMPLE_FACES_DIR}'.")
        print("Please add .jpg or .png images to this directory before running this script.")
        return 1
    
    print(f"Found {len(sample_images)} sample face images.")
    
    try:
        conn = sqlite3.connect(args.database)
        
        if args.reset:
            print("Removing all previously generated students...")
            clear_generated_students(conn)
        
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