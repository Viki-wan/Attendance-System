"""
Utility functions for generating fake data
"""
import random
import hashlib
from datetime import datetime, timedelta
from faker_config import *

def generate_email(first_name, last_name, domain="university.ac.ke"):
    """Generate email from name"""
    return f"{first_name.lower()}.{last_name.lower()}@{domain}"

def generate_kenyan_phone():
    """Generate Kenyan phone number format"""
    prefixes = ["0712", "0722", "0733", "0745", "0756", "0768", "0790", "0791", "0792", "0793"]
    prefix = random.choice(prefixes)
    number = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{prefix}{number}"

def hash_password(password):
    """Simple password hashing (use proper hashing in production)"""
    return hashlib.sha256(password.encode()).hexdigest()

def make_year_level(year, semester):
    """Create year_level in format: 4.2 (year 4, semester 2)"""
    return f"{year}.{semester}"

def generate_kenyan_name():
    """Generate a Kenyan name"""
    first_name = random.choice(KENYAN_FIRST_NAMES)
    last_name = random.choice(KENYAN_LAST_NAMES)
    # Ensure first and last name are different
    while first_name == last_name:
        last_name = random.choice(KENYAN_LAST_NAMES)
    return first_name, last_name

def get_semester_dates(semester):
    """Get start and end dates for a semester (semester is 1 or 2)"""
    if semester == 1:
        return SEMESTER_1_START, SEMESTER_1_END
    else:  # 2
        return SEMESTER_2_START, SEMESTER_2_END

def is_holiday(date):
    """Check if date is a holiday"""
    date_str = date.strftime("%Y-%m-%d")
    return any(holiday[0] == date_str for holiday in KENYAN_HOLIDAYS)

def get_teaching_dates(semester, day_of_week):
    """
    Get all teaching dates for a specific day of the week in a semester
    Excludes holidays
    """
    start_date, end_date = get_semester_dates(semester)
    dates = []
    
    # Find first occurrence of the day
    current = start_date
    while current.weekday() != (day_of_week - 1) % 7:  # Adjust for Monday=0 in weekday()
        current += timedelta(days=1)
    
    # Collect all occurrences
    while current <= end_date:
        if not is_holiday(current):
            dates.append(current)
        current += timedelta(weeks=1)
    
    return dates

def times_overlap(start1, end1, start2, end2):
    """Check if two time ranges overlap"""
    # Convert time strings to comparable format
    s1 = datetime.strptime(start1, "%H:%M").time()
    e1 = datetime.strptime(end1, "%H:%M").time()
    s2 = datetime.strptime(start2, "%H:%M").time()
    e2 = datetime.strptime(end2, "%H:%M").time()
    
    return not (e1 <= s2 or e2 <= s1)

def generate_class_code(course_code, year_level, sequence):
    """
    Generate class code in format: COMP 122
    Where first digit is year level
    """
    prefix = COURSES[course_code]["code_prefix"]
    return f"{prefix} {year_level}{sequence:02d}"

def get_year_from_class_code(class_code):
    """Extract year level from class code (e.g., 'COMP 122' -> 1)"""
    # Get the numeric part after the space
    numeric_part = class_code.split()[1]
    # First digit is the year
    return int(numeric_part[0])

def distribute_classes_to_instructor(total_classes, year_distribution_weights=None):
    """
    Distribute classes across years for an instructor
    Returns dict: {year_level: num_classes}
    """
    if year_distribution_weights is None:
        # Default: favor teaching lower years
        year_distribution_weights = {1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1}
    
    distribution = {1: 0, 2: 0, 3: 0, 4: 0}
    remaining = total_classes
    
    # Randomly distribute based on weights
    years = list(year_distribution_weights.keys())
    weights = list(year_distribution_weights.values())
    
    for _ in range(total_classes):
        if remaining <= 0:
            break
        year = random.choices(years, weights=weights)[0]
        # Max 2 classes per year level
        if distribution[year] < 2:
            distribution[year] += 1
            remaining -= 1
    
    return {k: v for k, v in distribution.items() if v > 0}

def calculate_session_duration(start_time, end_time):
    """Calculate duration in minutes between start and end time"""
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    duration = (end - start).seconds // 60
    return duration

def format_datetime_for_db(dt):
    """Format datetime for SQLite"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_date_for_db(dt):
    """Format date for SQLite"""
    return dt.strftime("%Y-%m-%d")

def format_time_for_db(time_str):
    """Ensure time is in HH:MM format"""
    return time_str

def get_classes_for_semester(all_classes, semester):
    """Filter classes that run in the given semester"""
    return [c for c in all_classes if c['semester'] == semester]

def validate_timetable_slot(timetable_entries, course_code, year_level, semester, day, start_time, end_time):
    """
    Check if a timetable slot is valid (no conflicts for same course year/semester)
    """
    for entry in timetable_entries:
        # Check if same course, year, semester, and day
        if (entry['course_code'] == course_code and 
            entry['year_level'] == year_level and
            entry['semester'] == semester and
            entry['day_of_week'] == day):
            # Check time overlap
            if times_overlap(start_time, end_time, entry['start_time'], entry['end_time']):
                return False
    return True

def select_random_time_slot(exclude_slots=None):
    """
    Select a random time slot, optionally excluding certain slots
    """
    available_slots = TIME_SLOTS.copy()
    
    if exclude_slots:
        available_slots = [slot for slot in available_slots 
                          if not any(times_overlap(slot[0], slot[1], ex[0], ex[1]) 
                                   for ex in exclude_slots)]
    
    if not available_slots:
        # If no slots available, return a random one anyway
        return random.choice(TIME_SLOTS)
    
    return random.choice(available_slots)