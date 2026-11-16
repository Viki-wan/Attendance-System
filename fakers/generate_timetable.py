"""
Generate timetable ensuring no conflicts for same course/year/semester
Includes classes for both semester 1 and semester 2
"""
import sqlite3
import random
from faker_config import *
from faker_utils import *
from datetime import datetime

def generate_timetable(db_path=DB_PATH):
    """Generate timetable for both semester 1 and semester 2 classes"""
    print("=" * 50)
    print("GENERATING TIMETABLE (BOTH SEMESTERS)")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all classes from both semesters
    cursor.execute("""
        SELECT class_id, course_code, class_name, year_level, semester
        FROM classes
        ORDER BY semester, course_code, year_level
    """)
    all_classes = cursor.fetchall()
    
    # Separate by semester
    sem1_classes = [c for c in all_classes if c[4] == 1]
    sem2_classes = [c for c in all_classes if c[4] == 2]
    
    print(f"\nFound {len(sem1_classes)} semester 1 classes to schedule")
    print(f"Found {len(sem2_classes)} semester 2 classes to schedule")
    print(f"Total: {len(all_classes)} classes\n")
    
    timetable_data = []
    
    # Process each semester separately
    for semester in [1, 2]:
        semester_classes = sem1_classes if semester == 1 else sem2_classes
        
        if not semester_classes:
            print(f"\nNo classes found for semester {semester}, skipping...")
            continue
            
        print(f"\n{'=' * 50}")
        print(f"PROCESSING SEMESTER {semester}")
        print(f"{'=' * 50}")
        
        # Track occupied slots per course/year/day for this semester
        # Key: (course_code, year_level, day_of_week)
        # Value: list of (start_time, end_time) tuples
        occupied_slots = {}
        
        # Group classes by course and year
        classes_by_group = {}
        for class_data in semester_classes:
            class_id, course_code, class_name, year_level, sem = class_data
            key = (course_code, year_level)
            if key not in classes_by_group:
                classes_by_group[key] = []
            classes_by_group[key].append(class_data)
        
        # Get semester dates for effective dates
        start_date, end_date = get_semester_dates(semester)
        print(f"\nSemester {semester} Period: {format_date_for_db(start_date)} to {format_date_for_db(end_date)}\n")
        
        # Process each group
        for (course_code, year_level), classes in classes_by_group.items():
            print(f"\n{course_code} - Year {year_level} (Semester {semester})")
            print(f"  Scheduling {len(classes)} classes...")
            
            # Assign each class to a day and time
            for class_data in classes:
                class_id, _, class_name, _, _ = class_data
                
                # Try to find a valid slot
                max_attempts = 50
                assigned = False
                
                for attempt in range(max_attempts):
                    # Random day (Monday-Friday)
                    day_of_week = random.choice(TEACHING_DAYS)
                    
                    # Random time slot
                    start_time, end_time = random.choice(TIME_SLOTS)
                    
                    # Check if slot is available
                    slot_key = (course_code, year_level, day_of_week)
                    
                    if slot_key not in occupied_slots:
                        occupied_slots[slot_key] = []
                    
                    # Check for conflicts
                    conflict = False
                    for occupied_start, occupied_end in occupied_slots[slot_key]:
                        if times_overlap(start_time, end_time, occupied_start, occupied_end):
                            conflict = True
                            break
                    
                    if not conflict:
                        # Assign this slot
                        occupied_slots[slot_key].append((start_time, end_time))
                        
                        timetable_entry = {
                            'class_id': class_id,
                            'day_of_week': day_of_week,
                            'start_time': start_time,
                            'end_time': end_time,
                            'is_active': True,
                            'effective_from': format_date_for_db(start_date),
                            'effective_to': format_date_for_db(end_date)
                        }
                        
                        timetable_data.append(timetable_entry)
                        
                        day_name = DAYS_OF_WEEK[day_of_week]
                        print(f"    ✓ {class_id} ({class_name}): {day_name} {start_time}-{end_time}")
                        assigned = True
                        break
                
                if not assigned:
                    print(f"    ⚠ Could not assign {class_id} ({class_name}) after {max_attempts} attempts")
    
    # Insert into database
    if timetable_data:
        cursor.executemany("""
            INSERT INTO timetable 
            (class_id, day_of_week, start_time, end_time, is_active, effective_from, effective_to)
            VALUES (:class_id, :day_of_week, :start_time, :end_time, :is_active, 
                    :effective_from, :effective_to)
        """, timetable_data)
        
        conn.commit()
    
    # Print summary statistics
    print(f"\n{'=' * 50}")
    print("TIMETABLE SUMMARY")
    print(f"{'=' * 50}")
    
    # Summary by semester
    for semester in [1, 2]:
        print(f"\n--- SEMESTER {semester} ---")
        
        cursor.execute("""
            SELECT c.course_code, c.year_level, COUNT(*) as class_count
            FROM timetable t
            JOIN classes c ON c.class_id = t.class_id
            WHERE c.semester = ?
            GROUP BY c.course_code, c.year_level
            ORDER BY c.course_code, c.year_level
        """, (semester,))
        
        summary = cursor.fetchall()
        if summary:
            print(f"\nClasses scheduled by course and year:")
            for row in summary:
                course_code, year_level, count = row
                print(f"  {course_code} Year {year_level}: {count} classes")
        else:
            print(f"  No classes scheduled for semester {semester}")
        
        # Summary by day
        cursor.execute("""
            SELECT t.day_of_week, COUNT(*) as class_count
            FROM timetable t
            JOIN classes c ON c.class_id = t.class_id
            WHERE c.semester = ?
            GROUP BY t.day_of_week
            ORDER BY t.day_of_week
        """, (semester,))
        
        day_summary = cursor.fetchall()
        if day_summary:
            print(f"\nClasses by day of week:")
            for day_num, count in day_summary:
                day_name = DAYS_OF_WEEK[day_num]
                print(f"  {day_name}: {count} classes")
    
    # Overall statistics
    cursor.execute("""
        SELECT COUNT(DISTINCT c.semester) as semesters,
               COUNT(DISTINCT c.course_code) as courses,
               COUNT(DISTINCT c.year_level) as years,
               COUNT(*) as total_classes
        FROM timetable t
        JOIN classes c ON c.class_id = t.class_id
    """)
    
    totals = cursor.fetchone()
    print(f"\n{'=' * 50}")
    print("OVERALL STATISTICS")
    print(f"{'=' * 50}")
    print(f"  Semesters: {totals[0]}")
    print(f"  Courses: {totals[1]}")
    print(f"  Year levels: {totals[2]}")
    print(f"  Total classes scheduled: {totals[3]}")
    
    conn.close()
    
    print(f"\n✓ Successfully generated {len(timetable_data)} timetable entries for both semesters")
    return timetable_data

if __name__ == "__main__":
    generate_timetable()