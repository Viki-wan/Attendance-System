"""
Faker Configuration and Constants
"""
from datetime import datetime, timedelta

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

# Course names by year level
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

# ==================== KENYAN NAMES ====================

KENYAN_FIRST_NAMES = [
    # Male names
    "Kamau", "Otieno", "Mwangi", "Odhiambo", "Njoroge", "Kipchoge", "Wanjiru", "Kariuki",
    "Kimani", "Omondi", "Kiprotich", "Mutua", "Owino", "Kiplagat", "Ndungu", "Onyango",
    "Kiptoo", "Muigai", "Ombati", "Cheruiyot", "Gitau", "Okoth", "Rotich", "Karanja",
    "Ouma", "Korir", "Githui", "Achieng", "Kemboi", "Muchiri", "Obiero", "Chepkwony",
    # Female names
    "Wanjiku", "Akinyi", "Wambui", "Adhiambo", "Njeri", "Cheptoo", "Wairimu", "Anyango",
    "Mumbi", "Jepkorir", "Nyambura", "Atieno", "Muthoni", "Chemutai", "Wangari", "Awuor",
    "Wacu", "Jelagat", "Wangui", "Akello", "Nyokabi", "Chepkoech", "Wanjiru", "Nekesa"
]

KENYAN_LAST_NAMES = [
    "Kamau", "Otieno", "Mwangi", "Odhiambo", "Njoroge", "Kipchoge", "Kariuki", "Kimani",
    "Omondi", "Kiprotich", "Mutua", "Owino", "Kiplagat", "Ndungu", "Onyango", "Kiptoo",
    "Muigai", "Ombati", "Cheruiyot", "Gitau", "Okoth", "Rotich", "Karanja", "Ouma",
    "Korir", "Githui", "Kemboi", "Muchiri", "Obiero", "Chepkwony", "Wanyama", "Okello",
    "Kiptanui", "Macharia", "Ochola", "Rono", "Githae", "Ogutu", "Kibet", "Maina",
    "Ombui", "Sang", "Waititu", "Oyugi", "Lagat", "Muturi", "Otieno", "Kogo"
]

# ==================== TIME SLOTS ====================

# Standard class time slots (avoiding lunch 12-2pm)
TIME_SLOTS = [
    ("08:00", "11:00"),  # Morning session
    ("08:30", "11:30"),
    ("09:00", "12:00"),
    ("11:00", "14:00"),  # Late morning into afternoon
    ("14:00", "17:00"),  # Afternoon session
    ("14:30", "17:30"),
    ("15:00", "18:00"),
]

DAYS_OF_WEEK = {
    0: "Sunday",
    1: "Monday", 
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday"
}

# Teaching days (Monday to Friday)
TEACHING_DAYS = [1, 2, 3, 4, 5]

# ==================== ACADEMIC CALENDAR ====================

# Current academic year
CURRENT_YEAR = 2025
ACADEMIC_YEAR = f"{CURRENT_YEAR}/{CURRENT_YEAR + 1}"

# Semester dates
SEMESTER_1_START = datetime(2025, 9, 2)   # September
SEMESTER_1_END = datetime(2025, 12, 20)   # December
SEMESTER_2_START = datetime(2026, 1, 13)  # January
SEMESTER_2_END = datetime(2026, 4, 30)    # April

# Determine current semester based on current date
def get_current_semester():
    """Determine current semester based on date (returns 1 or 2)"""
    now = datetime.now()
    if SEMESTER_1_START <= now <= SEMESTER_1_END:
        return 1
    elif SEMESTER_2_START <= now <= SEMESTER_2_END:
        return 2
    else:
        # Default to semester 2 if between semesters
        return 2

CURRENT_SEMESTER = get_current_semester()

# Kenyan Public Holidays 2024-2025
KENYAN_HOLIDAYS = [
    ("2024-10-10", "Utamaduni Day"),
    ("2024-10-20", "Mashujaa Day"),
    ("2024-12-12", "Jamhuri Day"),
    ("2024-12-25", "Christmas Day"),
    ("2024-12-26", "Boxing Day"),
    ("2025-01-01", "New Year's Day"),
    ("2025-04-18", "Good Friday"),
    ("2025-04-21", "Easter Monday"),
    ("2025-05-01", "Labour Day"),
    ("2025-06-01", "Madaraka Day"),
]

# ==================== DATABASE CONFIG ====================

DB_PATH = "attendance.db"
INSTRUCTOR_ID_PREFIX = "L"
INSTRUCTOR_START_NUMBER = 2025001

# Note: Instructor ID is used as default password for first login