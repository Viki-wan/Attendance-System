"""
Faker Configuration
Shared configuration and utilities for all faker scripts
"""

from datetime import datetime, date, timedelta
import random

# ==================== FACULTY & COURSES ====================

FACULTY = "Science"
FACULTY_CODE = "S"

COURSES = {
    "S11": {
        "name": "Bachelor of Science in Science",
        "years": 4,
        "code_prefix": "SCI"
    },
    "S12": {
        "name": "Bachelor of Science in Biomedical Science and Technology",
        "years": 4,
        "code_prefix": "BIOM"
    },
    "S13": {
        "name": "Bachelor of Science in Computer Science",
        "years": 4,
        "code_prefix": "COMP"
    },
    "S14": {
        "name": "Bachelor of Science in Biochemistry",
        "years": 4,
        "code_prefix": "BCHM"
    },
    "S18": {
        "name": "Bachelor of Science in Statistics",
        "years": 4,
        "code_prefix": "STAT"
    },
    "S19": {
        "name": "Bachelor of Science in Actuarial Sciences",
        "years": 4,
        "code_prefix": "ACTU"
    }
}

# ==================== ACADEMIC CALENDAR ====================

# Get current date
_TODAY = datetime.now().date()

def _get_current_academic_year():
    """Determine current academic year based on today's date"""
    year = _TODAY.year
    month = _TODAY.month
    # Academic year starts in September
    if month >= 9:
        return year
    else:
        return year - 1

def _get_semester_dates(academic_year):
    """Generate semester dates for the given academic year"""
    return {
        "1.1": {"start": f"{academic_year}-09-02", "end": f"{academic_year}-11-15"},  # Sept - Nov
        "1.2": {"start": f"{academic_year}-11-18", "end": f"{academic_year + 1}-02-07"},  # Nov - Feb
        "2.1": {"start": f"{academic_year + 1}-02-10", "end": f"{academic_year + 1}-04-25"},  # Feb - Apr
        "2.2": {"start": f"{academic_year + 1}-04-28", "end": f"{academic_year + 1}-07-18"},  # Apr - Jul
    }

def _get_current_semester(semester_dates):
    """Determine current semester based on today's date"""
    for sem, dates in semester_dates.items():
        start = datetime.strptime(dates["start"], "%Y-%m-%d").date()
        end = datetime.strptime(dates["end"], "%Y-%m-%d").date()
        if start <= _TODAY <= end:
            return sem
    # Default to first semester if not in any range
    return "1.1"

def _get_holidays(academic_year):
    """Generate holiday dates for current and next academic year"""
    next_year = academic_year + 1
    return [
        {"name": "Mashujaa Day", "date": f"{academic_year}-10-20", "recurring": True},
        {"name": "Christmas Day", "date": f"{academic_year}-12-25", "recurring": True},
        {"name": "Boxing Day", "date": f"{academic_year}-12-26", "recurring": True},
        {"name": "New Year's Day", "date": f"{next_year}-01-01", "recurring": True},
        {"name": "Good Friday", "date": f"{next_year}-04-18", "recurring": False},  # Approximate
        {"name": "Easter Monday", "date": f"{next_year}-04-21", "recurring": False},  # Approximate
        {"name": "Labour Day", "date": f"{next_year}-05-01", "recurring": True},
        {"name": "Madaraka Day", "date": f"{next_year}-06-01", "recurring": True},
    ]

# Current academic year settings (automatically determined)
CURRENT_YEAR = _get_current_academic_year()
SEMESTER_DATES = _get_semester_dates(CURRENT_YEAR)
CURRENT_SEMESTER = _get_current_semester(SEMESTER_DATES)
HOLIDAYS = _get_holidays(CURRENT_YEAR)

# Semester structure (each year has 2 semesters, each semester has 2 parts)
SEMESTERS = ["1.1", "1.2", "2.1", "2.2"]

# ==================== CLASS SCHEDULES ====================

# Time slots for classes (Kenyan university schedule)
TIME_SLOTS = [
    ("08:00", "09:00"),  # Early morning
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:00", "12:00"),
    ("12:00", "13:00"),  # Lunch break usually here
    ("13:00", "14:00"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
    ("16:00", "17:00"),
    ("17:00", "18:00"),  # Evening classes
]

# Days of week (0=Sunday, 1=Monday, ..., 6=Saturday)
WEEKDAYS = [1, 2, 3, 4, 5]  # Monday to Friday
DAY_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday"
}

# ==================== COURSE CLASS TEMPLATES ====================

# Expanded course names by prefix and year with more variety
COURSE_NAMES = {
    "S13": {  # Computer Science
        1: [
            "Introduction to Programming", "Computer Fundamentals", "Digital Systems",
            "Programming Logic", "Computing Essentials", "IT Foundations",
            "Computational Thinking", "Logic & Problem Solving", "Introduction to Algorithms",
            "Digital Literacy", "Computer Systems Overview", "Web Development Basics"
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
    "S11": {  # General Science
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
    "S12": {  # Biomedical Science
        1: [
            "Introduction to Biomedical Science", "Human Anatomy I", "Medical Biochemistry I",
            "Cell Biology", "Medical Terminology", "Laboratory Techniques",
            "Introduction to Physiology", "Medical Ethics", "Basic Microbiology",
            "Human Biology", "Health Sciences Foundation", "Medical Research Methods"
        ],
        2: [
            "Molecular Biology", "Medical Microbiology", "Human Anatomy II",
            "Medical Biochemistry II", "Pathology", "Immunology",
            "Pharmacology Basics", "Clinical Laboratory Methods", "Medical Genetics",
            "Tissue Biology", "Medical Instrumentation", "Biomedical Statistics"
        ],
        3: [
            "Clinical Biochemistry", "Medical Diagnostics", "Hematology",
            "Advanced Immunology", "Medical Biotechnology", "Parasitology",
            "Clinical Microbiology", "Medical Imaging", "Toxicology",
            "Cancer Biology", "Medical Informatics", "Research Design"
        ],
        4: [
            "Advanced Pathology", "Clinical Trials", "Biomedical Research Project",
            "Medical Biotechnology Applications", "Advanced Diagnostics", "Pharmacogenetics",
            "Molecular Diagnostics", "Medical Laboratory Management", "Translational Medicine",
            "Biomedical Innovation", "Advanced Clinical Methods", "Healthcare Technology"
        ]
    },
    "S14": {  # Biochemistry
        1: [
            "General Biochemistry I", "Organic Chemistry I", "General Biology",
            "Basic Chemistry", "Introduction to Biochemistry", "Laboratory Skills",
            "Chemical Principles", "Biochemical Foundations", "Molecular Biology Basics",
            "Chemistry for Life Sciences", "Biochemical Techniques", "Scientific Writing"
        ],
        2: [
            "Organic Chemistry II", "Analytical Chemistry", "Biochemistry II",
            "Physical Chemistry", "Enzymology", "Metabolism",
            "Biochemical Analysis", "Molecular Genetics", "Protein Chemistry",
            "Instrumental Analysis", "Bioenergetics", "Chemical Biology"
        ],
        3: [
            "Advanced Biochemistry", "Molecular Biology", "Biotechnology",
            "Pharmaceutical Chemistry", "Industrial Biochemistry", "Bioinformatics",
            "Advanced Metabolism", "Biochemical Regulation", "Structural Biology",
            "Clinical Biochemistry", "Plant Biochemistry", "Membrane Biology"
        ],
        4: [
            "Biochemical Research Methods", "Advanced Biotechnology", "Drug Design",
            "Biochemical Engineering", "Advanced Molecular Biology", "Proteomics",
            "Genomics", "Metabolomics", "Systems Biology",
            "Biochemistry Research Project", "Industrial Applications", "Regulatory Biochemistry"
        ]
    },
    "S18": {  # Statistics
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
    "S19": {  # Actuarial Science
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
    }
}

# ==================== INSTRUCTOR DATA ====================

INSTRUCTOR_NAMES = [
    "Dr. James Kamau",
    "Dr. Mary Wanjiku",
    "Prof. Peter Omondi",
    "Dr. Grace Njeri",
    "Mr. David Mwangi",
    "Dr. Sarah Akinyi",
    "Prof. John Kipruto",
    "Dr. Rebecca Mutua",
    "Mr. Michael Otieno",
    "Dr. Catherine Wambui",
    "Prof. Daniel Kiplagat",
    "Dr. Lucy Nyambura",
    "Mr. Patrick Okello",
    "Dr. Jane Chebet",
    "Prof. Samuel Kimani"
]

# ==================== STUDENT NAMING ====================

FIRST_NAMES = [
    "Brian", "Kevin", "Dennis", "Eric", "Felix", "George", "Henry", "Ian", "Jack", "Keith",
    "Leonard", "Martin", "Nathan", "Oscar", "Paul", "Quincy", "Robert", "Steven", "Thomas", "Victor",
    "Alice", "Betty", "Caroline", "Diana", "Emma", "Faith", "Grace", "Hannah", "Irene", "Joyce",
    "Karen", "Laura", "Mary", "Nancy", "Olive", "Patience", "Queen", "Ruth", "Sarah", "Tracy"
]

LAST_NAMES = [
    "Kamau", "Wanjiru", "Mwangi", "Njeri", "Kariuki", "Wambui", "Kimani", "Nyambura",
    "Ochieng", "Otieno", "Akinyi", "Adhiambo", "Okello", "Wafula", "Juma", "Barasa",
    "Kiplagat", "Chebet", "Rotich", "Biwott", "Tanui", "Kipruto", "Chepkemoi", "Jepkorir",
    "Mohamed", "Hassan", "Ali", "Fatuma", "Rashid", "Salim", "Noor", "Amina"
]

# ==================== UTILITY FUNCTIONS ====================

def get_academic_year_for_date(target_date):
    """Determine which academic year a date falls into"""
    year = target_date.year
    month = target_date.month
    
    # Academic year starts in September
    if month >= 9:
        return year
    else:
        return year - 1

def get_semester_for_date(target_date):
    """Determine which semester a date falls into"""
    for sem, dates in SEMESTER_DATES.items():
        start = datetime.strptime(dates["start"], "%Y-%m-%d").date()
        end = datetime.strptime(dates["end"], "%Y-%m-%d").date()
        if start <= target_date <= end:
            return sem
    return CURRENT_SEMESTER

def is_holiday(check_date):
    """Check if a date is a holiday"""
    for holiday in HOLIDAYS:
        holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
        if holiday["recurring"]:
            if holiday_date.month == check_date.month and holiday_date.day == check_date.day:
                return True
        else:
            if holiday_date == check_date:
                return True
    return False

def is_weekend(check_date):
    """Check if date is weekend"""
    return check_date.weekday() in [5, 6]  # Saturday, Sunday

def generate_student_id(course_code, year_of_admission, sequence):
    """
    Generate student ID in format: COURSE-YEAR-SEQUENCE
    Example: S13-2021-001 (Computer Science, admitted 2021, student #1)
    """
    return f"{course_code}-{year_of_admission}-{sequence:03d}"

def generate_instructor_id(sequence):
    """
    Generate instructor ID in format: L + YEAR + SEQUENCE
    Example: L2025003 (Lecturer hired in 2025, #3)
    """
    return f"L{CURRENT_YEAR}{sequence:03d}"

def generate_class_id(course_code, year, semester):
    """
    Generate class ID
    Example: S13-Y1-S1.1 (Computer Science, Year 1, Semester 1.1)
    """
    return f"{course_code}-Y{year}-S{semester}"

def get_class_code(course_code, class_num, year):
    """
    Generate class code in format: PREFIX + YEAR_DIGIT + CLASS_NUM
    Example: COMP122 (Computer Science, Year 1, Class #22)
    """
    prefix = COURSES[course_code]["code_prefix"]
    year_digit = year
    return f"{prefix}{year_digit}{class_num:02d}"

def get_email(name, domain="students.university.ac.ke"):
    """Generate email from name"""
    name_parts = name.lower().split()
    if len(name_parts) >= 2:
        return f"{name_parts[0]}.{name_parts[1]}@{domain}"
    return f"{name_parts[0]}@{domain}"

def generate_phone():
    """Generate Kenyan phone number"""
    prefixes = ["0710", "0720", "0730", "0740", "0750", "0768", "0769"]
    return f"{random.choice(prefixes)}{random.randint(100000, 999999)}"

# ==================== DATE RANGES ====================

def get_date_range_for_semester(semester, academic_year=CURRENT_YEAR):
    """Get start and end dates for a semester"""
    semester_dates = _get_semester_dates(academic_year)
    dates = semester_dates.get(semester)
    if not dates:
        return None, None
    
    start_date = datetime.strptime(dates["start"], "%Y-%m-%d").date()
    end_date = datetime.strptime(dates["end"], "%Y-%m-%d").date()
    
    return start_date, end_date

def get_weekdays_in_range(start_date, end_date):
    """Get all weekdays (Mon-Fri) in a date range, excluding holidays"""
    current = start_date
    weekdays = []
    
    while current <= end_date:
        if not is_weekend(current) and not is_holiday(current):
            weekdays.append(current)
        current += timedelta(days=1)
    
    return weekdays

print("✅ Faker configuration loaded successfully!")
print(f"📅 Current Date: {_TODAY}")
print(f"📅 Current Academic Year: {CURRENT_YEAR}")
print(f"📚 Current Semester: {CURRENT_SEMESTER}")
print(f"🏫 Faculty: {FACULTY}")
print(f"📖 Courses: {len(COURSES)}")