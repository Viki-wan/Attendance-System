import sqlite3
import random
from faker import Faker
import re
import uuid

# Initialize faker
fake = Faker()

# Constants
DATABASE_PATH = "attendance.db"  # Update this to your actual database path
SEMESTERS_PER_YEAR = 2
CLASSES_PER_COURSE_PER_SEMESTER = 6
MAX_YEAR = 4  # Changed from 6 to 4 - Maximum year for courses (1-4)
SHARED_CLASSES_PER_SEMESTER = 2  # Maximum number of shared classes per semester for 1st year

# Map existing course codes to department prefixes
COURSE_MAPPING = {
    "S13": "COMP",     # SCIENCES
    "S11": "SCI",      # COMPUTER SCIENCE
    "S18": "STAT",     # STATISTICS
    "S19": "ACTS",     # ACTURIAL SCIENCE
    "S14": "ACS",      # APPLIED COMPUTER SCIENCE
    "S20": "MATH"      # PURE MATHS
}

# Expanded course names by prefix and year with more variety
COURSE_NAMES = {
    "COMP": {
        1: [
            "Introduction to Programming", "Computer Fundamentals", "Digital Systems", 
            "Programming Logic", "Computing Essentials", "IT Foundations",
            "Computational Thinking", "Logic & Problem Solving", "Computing in Society",
            "Introduction to Algorithms", "Digital Literacy", "Computer Systems Overview"
        ],
        2: [
            "Data Structures", "Web Development", "Database Systems", 
            "Object-Oriented Programming", "Computer Architecture", "Algorithms",
            "System Design", "Software Testing", "UI/UX Fundamentals",
            "Network Fundamentals", "API Design", "Mobile Computing Basics"
        ],
        3: [
            "Software Engineering", "Operating Systems", "Computer Networks", 
            "Mobile App Development", "System Analysis", "Cybersecurity",
            "Distributed Computing", "Full Stack Development", "Database Administration",
            "Network Security", "Agile Methodologies", "DevOps Practices"
        ],
        4: [
            "Artificial Intelligence", "Machine Learning", "Big Data Analytics", 
            "Cloud Computing", "Computer Vision", "Advanced Networking",
            "Natural Language Processing", "Quantum Information", "Parallel Programming",
            "Advanced Algorithms", "Information Retrieval", "High-Performance Computing"
        ]
    },
    "SCI": {
        1: [
            "General Biology", "Chemistry Fundamentals", "Physics I", 
            "Earth Science", "Environmental Science", "Science Lab Methods",
            "Scientific Reasoning", "Introduction to Scientific Methods", "Natural Sciences Survey",
            "Physical Sciences Overview", "Life Sciences Foundations", "Quantitative Methods in Science"
        ],
        2: [
            "Organic Chemistry", "Physics II", "Cell Biology", 
            "Scientific Computing", "Biochemistry", "Ecology",
            "Molecular Techniques", "Science & Technology", "Plant Biology",
            "Animal Physiology", "Analytical Methods", "Scientific Instrumentation"
        ],
        3: [
            "Molecular Biology", "Genetics", "Analytical Chemistry", 
            "Quantum Physics", "Microbiology", "Scientific Research Methods",
            "Conservation Biology", "Science Communication", "Applied Physics",
            "Biostatistics", "Evolutionary Biology", "Environmental Chemistry"
        ],
        4: [
            "Bioinformatics", "Physical Chemistry", "Advanced Physics", 
            "Evolutionary Biology", "Scientific Modeling", "Research Project I",
            "Advanced Molecular Biology", "Environmental Monitoring", "Advanced Biochemistry",
            "Theoretical Physics", "Scientific Programming", "Ecological Modeling"
        ]
    },
    "STAT": {
        1: [
            "Introduction to Statistics", "Statistical Methods", "Probability Theory", 
            "Data Collection", "Statistical Software", "Statistical Thinking",
            "Descriptive Statistics", "Inferential Statistics Basics", "Sampling Techniques",
            "Statistical Reasoning", "Data Visualization", "Numerical Methods in Statistics"
        ],
        2: [
            "Statistical Inference", "Regression Analysis", "Experimental Design", 
            "Applied Statistics", "Time Series Analysis", "Multivariate Analysis",
            "Statistical Computing", "Probability Models", "Survey Methods",
            "Business Statistics", "Biostatistics Fundamentals", "Statistical Quality Control"
        ],
        3: [
            "Statistical Computing", "Sampling Theory", "Statistical Learning", 
            "Bayesian Statistics", "Statistical Modeling", "Quality Control",
            "Advanced Regression", "Categorical Data Analysis", "Nonparametric Statistics",
            "Advanced Experimental Design", "Monte Carlo Methods", "Applied Probability"
        ],
        4: [
            "Advanced Statistical Methods", "Statistical Consulting", "Computational Statistics", 
            "Data Mining", "Stochastic Processes", "Survival Analysis",
            "Financial Statistics", "Applied Multivariate Analysis", "Statistical Decision Theory",
            "Predictive Analytics", "Time Series Forecasting", "Statistical Process Control"
        ]
    },
    "ACTS": {
        1: [
            "Introduction to Actuarial Science", "Financial Mathematics", "Economics for Actuaries", 
            "Business Statistics", "Professional Ethics", "Business Communication",
            "Probability for Actuaries", "Financial Accounting", "Insurance Principles",
            "Mathematical Foundations", "Professional Development", "Actuarial Problem Solving"
        ],
        2: [
            "Life Contingencies", "Non-life Insurance", "Corporate Finance", 
            "Financial Reporting", "Risk Management", "Actuarial Models",
            "Insurance Law", "Financial Economics", "Statistical Methods for Actuaries",
            "Actuarial Mathematics", "Business Risk Analysis", "Investment Theory"
        ],
        3: [
            "Survival Models", "Pension Funds", "Investment Theory", 
            "Actuarial Statistics", "Insurance Law", "Actuarial Data Analysis",
            "Health Insurance", "Advanced Life Contingencies", "Stochastic Modeling",
            "Credibility Theory", "Asset Liability Management", "Loss Models"
        ],
        4: [
            "Advanced Life Contingencies", "Enterprise Risk Management", "Advanced Pension Mathematics", 
            "Financial Economics", "Applied Stochastic Methods", "Actuarial Practice",
            "Quantitative Risk Management", "Actuarial Communications", "Insurance Portfolio Theory",
            "Advanced Financial Mathematics", "Reinsurance", "Actuarial Case Studies"
        ]
    },
    "ACS": {
        1: [
            "Applied Programming", "Computer Applications", "Applied IT", 
            "Technical Communication", "Visual Programming", "Applied Computing Fundamentals",
            "Business Computing", "Web Fundamentals", "Database Foundations",
            "Computing Ethics", "Information Systems Basics", "IT Support Skills"
        ],
        2: [
            "Applied Web Technologies", "Database Applications", "User Interface Design", 
            "Business Applications", "Project Management", "Applied Development Methods",
            "Enterprise Applications", "Systems Support", "Network Administration",
            "Mobile Technologies", "Cloud Fundamentals", "Business Intelligence Basics"
        ],
        3: [
            "Applied Software Engineering", "Applied Systems Analysis", "Business Intelligence", 
            "Applied Mobile Development", "IT Infrastructure", "Applied Network Systems",
            "Enterprise Systems Implementation", "Information Security", "Advanced Database Applications",
            "Cloud Services Management", "IT Project Leadership", "Systems Integration"
        ],
        4: [
            "Applied AI", "Data Warehousing", "Enterprise Systems", 
            "Digital Media Processing", "IT Governance", "Applied Computer Security",
            "IT Service Management", "Enterprise Architecture", "Business Process Modeling",
            "Industry Applications", "Information Management", "Advanced IT Infrastructure"
        ]
    },
    "MATH": {
        1: [
            "Calculus I", "Linear Algebra I", "Discrete Mathematics", 
            "Mathematical Reasoning", "Mathematical Software", "Introduction to Proofs",
            "Mathematical Foundations", "Mathematical Modeling", "Mathematics for Sciences",
            "Analytical Geometry", "Logic & Set Theory", "Mathematical Problem Solving"
        ],
        2: [
            "Calculus II", "Linear Algebra II", "Abstract Algebra I", 
            "Real Analysis I", "Differential Equations", "Mathematical Applications",
            "Probability Theory", "Mathematical Computing", "Vector Calculus",
            "Number Theory Basics", "Graph Theory", "Mathematical Statistics"
        ],
        3: [
            "Multivariable Calculus", "Complex Analysis", "Numerical Analysis", 
            "Abstract Algebra II", "Real Analysis II", "Topology",
            "Partial Differential Equations", "Applied Mathematics", "Dynamical Systems",
            "Mathematical Physics", "Operations Research", "Combinatorial Mathematics"
        ],
        4: [
            "Advanced Calculus", "Functional Analysis", "Mathematical Modeling", 
            "Number Theory", "Partial Differential Equations", "Algebraic Structures",
            "Mathematical Logic", "Cryptography", "Computational Mathematics",
            "Optimization Theory", "Financial Mathematics", "Mathematical Foundations of CS"
        ]
    }
}

# Dictionary to store already used class names to avoid duplicates
used_class_names = set()

def create_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_courses():
    """Get all courses from the database."""
    conn = create_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT course_code, course_name FROM courses")
        courses = cursor.fetchall()
        return courses
    except sqlite3.Error as e:
        print(f"Error getting courses: {e}")
        return []
    finally:
        conn.close()

def get_instructors():
    """Get all instructors from the database."""
    conn = create_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT instructor_id, instructor_name FROM instructors")
        instructors = cursor.fetchall()
        return instructors
    except sqlite3.Error as e:
        print(f"Error getting instructors: {e}")
        return []
    finally:
        conn.close()

def get_instructor_courses():
    """Get all instructor-course mappings."""
    conn = create_connection()
    if conn is None:
        return {}
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT instructor_id, course_code FROM instructor_courses")
        mappings = cursor.fetchall()
        
        result = {}
        for instructor_id, course_code in mappings:
            if course_code not in result:
                result[course_code] = []
            result[course_code].append(instructor_id)
        
        return result
    except sqlite3.Error as e:
        print(f"Error getting instructor courses: {e}")
        return {}
    finally:
        conn.close()

def get_department_prefix(course_code):
    """Convert course_code to department prefix."""
    # Try to find the code in our mapping
    if course_code in COURSE_MAPPING:
        return COURSE_MAPPING[course_code]
    
    # If not found, use the first part or a default
    match = re.match(r'^([A-Za-z]+)', course_code)
    if match:
        return match.group(1).upper()
    
    # Default if we can't determine
    return "DEPT"

def generate_unique_class_name(dept_prefix, year):
    """Generate a unique class name based on department and year."""
    if dept_prefix in COURSE_NAMES and year in COURSE_NAMES[dept_prefix]:
        available_names = [name for name in COURSE_NAMES[dept_prefix][year] if name not in used_class_names]
        
        # If we've used all predefined names, create a new unique one
        if not available_names:
            unique_name = f"{dept_prefix} {fake.word().capitalize()} {fake.word().capitalize()} {year}.{random.randint(1, 99)}"
            used_class_names.add(unique_name)
            return unique_name
        
        # Otherwise use an available predefined name
        name = random.choice(available_names)
        used_class_names.add(name)
        return name
    else:
        # Create a completely new name
        unique_name = f"{dept_prefix} {fake.word().capitalize()} {fake.word().capitalize()} {year}.{random.randint(1, 99)}"
        used_class_names.add(unique_name)
        return unique_name

def insert_class(conn, class_data, course_instructors):
    """Insert a class with its relationships."""
    try:
        cursor = conn.cursor()
        
        # Check if class_id already exists
        cursor.execute("SELECT COUNT(*) FROM classes WHERE class_id = ?", (class_data['class_id'],))
        if cursor.fetchone()[0] > 0:
            print(f"Class ID {class_data['class_id']} already exists. Skipping.")
            return False
        
        # Insert into classes table
        cursor.execute("""
            INSERT INTO classes (class_id, course_code, class_name, year, semester)
            VALUES (?, ?, ?, ?, ?)
        """, (
            class_data['class_id'],
            class_data['course_code'],
            class_data['class_name'],
            class_data['year'],
            class_data['semester']
        ))
        
        # Insert into class_courses table
        cursor.execute("""
            INSERT INTO class_courses (class_id, course_code)
            VALUES (?, ?)
        """, (
            class_data['class_id'],
            class_data['course_code']
        ))
        
        # For shared classes, add additional course relationships
        if 'shared_with' in class_data:
            for shared_course in class_data['shared_with']:
                cursor.execute("""
                    INSERT INTO class_courses (class_id, course_code)
                    VALUES (?, ?)
                """, (
                    class_data['class_id'],
                    shared_course
                ))
        
        # Randomly select 1-3 instructors for this class if available
        available_instructors = []
        if class_data['course_code'] in course_instructors:
            available_instructors.extend(course_instructors[class_data['course_code']])
        
        # Also consider instructors from shared courses
        if 'shared_with' in class_data:
            for shared_course in class_data['shared_with']:
                if shared_course in course_instructors:
                    available_instructors.extend(course_instructors[shared_course])
        
        # Remove duplicates
        available_instructors = list(set(available_instructors))
        
        if available_instructors:
            num_instructors = min(random.randint(1, 3), len(available_instructors))
            selected_instructors = random.sample(available_instructors, num_instructors)
            
            for instructor_id in selected_instructors:
                cursor.execute("""
                    INSERT INTO class_instructors (class_id, instructor_id)
                    VALUES (?, ?)
                """, (
                    class_data['class_id'],
                    instructor_id
                ))
        
        return True
    except sqlite3.Error as e:
        print(f"Error inserting class: {e}")
        return False

def delete_existing_classes(conn):
    """Remove existing classes for clean insertion."""
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM class_instructors")
        cursor.execute("DELETE FROM class_courses")
        cursor.execute("DELETE FROM classes")
        return True
    except sqlite3.Error as e:
        print(f"Error deleting existing classes: {e}")
        return False

def main():
    # Connect to database
    conn = create_connection()
    if conn is None:
        return
    
    try:
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Get existing data
        courses = get_courses()
        instructors = get_instructors()
        course_instructors = get_instructor_courses()
        
        # Optionally clear existing classes
        if delete_existing_classes(conn):
            print("Deleted existing classes.")
        
        # Track generated classes
        generated_classes = 0
        used_class_ids = set()
        
        # Store shared classes for year 1
        shared_classes_by_semester = {}
        
        # First, generate shared first-year classes
        if len(courses) >= 2:  # We need at least 2 courses to share classes
            first_year_courses = [code for code, _ in courses]
            
            for semester_num in range(1, SEMESTERS_PER_YEAR + 1):
                semester = f"1.{semester_num}"  # Only for first year
                shared_classes_by_semester[semester] = []
                
                # Generate shared classes for this semester
                for i in range(SHARED_CLASSES_PER_SEMESTER):
                    # Select 2-3 random courses to share this class
                    num_courses_to_share = min(random.randint(2, 3), len(first_year_courses))
                    shared_courses = random.sample(first_year_courses, num_courses_to_share)
                    primary_course = shared_courses[0]
                    shared_with = shared_courses[1:]
                    
                    # Get department prefix based on primary course code
                    dept_prefix = get_department_prefix(primary_course)
                    
                    # Generate a unique class ID
                    while True:
                        class_number = f"1{random.randint(0, 9)}{random.randint(0, 9)}"
                        class_id = f"{dept_prefix} {class_number}"
                        
                        if class_id not in used_class_ids:
                            used_class_ids.add(class_id)
                            break
                    
                    # Generate a unique class name
                    class_name = generate_unique_class_name(dept_prefix, 1)
                    
                    # Create shared class data
                    class_data = {
                        'class_id': class_id,
                        'course_code': primary_course,
                        'class_name': class_name,
                        'year': 1,
                        'semester': semester,
                        'shared_with': shared_with
                    }
                    
                    # Store for tracking
                    shared_classes_by_semester[semester].append({
                        'class_data': class_data,
                        'shared_courses': shared_courses
                    })
                    
                    # Insert shared class
                    if insert_class(conn, class_data, course_instructors):
                        generated_classes += 1
                        print(f"Generated shared class {class_id} for courses: {', '.join(shared_courses)}")
        
        # Now generate regular classes for all courses, years, and semesters
        for course_code, course_name in courses:
            # Get department prefix based on course code
            dept_prefix = get_department_prefix(course_code)
            
            # For each year (1-4)
            for year in range(1, MAX_YEAR + 1):
                # For each semester (e.g., 1.1, 1.2, etc.)
                for semester_num in range(1, SEMESTERS_PER_YEAR + 1):
                    semester = f"{year}.{semester_num}"
                    
                    # Number of classes to generate for this course in this semester
                    classes_to_generate = CLASSES_PER_COURSE_PER_SEMESTER
                    
                    # If this is year 1 and we have shared classes, reduce the number of regular classes
                    if year == 1:
                        shared_classes = shared_classes_by_semester.get(semester, [])
                        courses_with_shared_classes = []
                        for shared_class in shared_classes:
                            courses_with_shared_classes.extend(shared_class['shared_courses'])
                        
                        # Count how many shared classes this course already has
                        shared_count = courses_with_shared_classes.count(course_code)
                        classes_to_generate -= shared_count
                    
                    # Generate regular classes
                    for i in range(classes_to_generate):
                        # Generate a unique class ID
                        while True:
                            class_number = f"{year}{random.randint(0, 9)}{random.randint(0, 9)}"
                            class_id = f"{dept_prefix} {class_number}"
                            
                            if class_id not in used_class_ids:
                                used_class_ids.add(class_id)
                                break
                        
                        # Generate a unique class name
                        class_name = generate_unique_class_name(dept_prefix, year)
                        
                        # Create class data
                        class_data = {
                            'class_id': class_id,
                            'course_code': course_code,
                            'class_name': class_name,
                            'year': year,
                            'semester': semester
                        }
                        
                        # Insert regular class
                        if insert_class(conn, class_data, course_instructors):
                            generated_classes += 1
                            if generated_classes % 10 == 0:
                                print(f"Generated {generated_classes} classes...")
        
        # Commit transaction
        conn.commit()
        print(f"Successfully generated {generated_classes} classes with unique names.")
        
    except Exception as e:
        # Rollback in case of error
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()