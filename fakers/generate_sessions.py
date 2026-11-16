"""
Generate class sessions from timetable with realistic statuses
Sessions are created for each scheduled day in the semester
Status: scheduled, ongoing, completed, cancelled, missed, dismissed
"""
import sqlite3
import random
from faker_config import *
from faker_utils import *
from datetime import datetime, timedelta

def determine_session_status(session_date, session_start_time, session_end_time, current_datetime):
    """
    Determine realistic session status based on date and time
    Returns: 'scheduled', 'ongoing', 'completed', 'cancelled', 'missed', 'dismissed'
    """
    # Parse session times to create full datetime objects
    start_hour, start_min = map(int, session_start_time.split(':'))
    end_hour, end_min = map(int, session_end_time.split(':'))
    
    session_start_datetime = datetime.combine(session_date, datetime.min.time().replace(hour=start_hour, minute=start_min))
    session_end_datetime = datetime.combine(session_date, datetime.min.time().replace(hour=end_hour, minute=end_min))
    
    # Future sessions (date is in the future)
    if session_date > current_datetime.date():
        return 'scheduled'
    
    # Today's session - check actual time
    elif session_date == current_datetime.date():
        # If current time is before session starts, it's scheduled
        if current_datetime < session_start_datetime:
            return 'scheduled'
        # If current time is during the session, it's ongoing
        elif session_start_datetime <= current_datetime <= session_end_datetime:
            return 'ongoing'
        # If current time is after session ended, apply realistic distribution
        else:
            rand = random.random()
            if rand < 0.85:
                return 'completed'
            elif rand < 0.90:
                return 'dismissed'
            elif rand < 0.95:
                return 'cancelled'
            else:
                return 'missed'
    
    # Future datetime (safety check for edge cases)
    elif session_start_datetime > current_datetime:
        return 'scheduled'
    
    # Past sessions - apply realistic distribution
    else:
        # Weight the probabilities for realistic outcomes
        # Most sessions should be completed, with occasional issues
        rand = random.random()
        
        if rand < 0.85:  # 85% completed normally
            return 'completed'
        elif rand < 0.90:  # 5% dismissed (instructor issue)
            return 'dismissed'
        elif rand < 0.95:  # 5% cancelled (planned)
            return 'cancelled'
        else:  # 5% missed (unplanned absence)
            return 'missed'

def generate_sessions_from_timetable(db_path=DB_PATH):
    """Generate class sessions based on timetable with realistic statuses"""
    print("=" * 50)
    print("GENERATING CLASS SESSIONS FROM TIMETABLE")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all timetable entries with class and instructor info
    # Use MIN(instructor_id) to get one instructor per class if multiple exist
    cursor.execute("""
        SELECT 
            t.class_id,
            t.day_of_week,
            t.start_time,
            t.end_time,
            t.effective_from,
            t.effective_to,
            c.course_code,
            c.class_name,
            c.semester,
            MIN(ci.instructor_id) as instructor_id
        FROM timetable t
        JOIN classes c ON c.class_id = t.class_id
        JOIN class_instructors ci ON ci.class_id = t.class_id
        WHERE t.is_active = 1
        GROUP BY t.class_id, t.day_of_week, t.start_time, t.end_time,
                 t.effective_from, t.effective_to, c.course_code, 
                 c.class_name, c.semester
        ORDER BY c.course_code, c.year_level
    """)
    
    timetable_entries = cursor.fetchall()
    
    session_data = []
    session_counter = 1
    current_datetime = datetime.now()
    
    # Get holidays
    holiday_dates = [datetime.strptime(h[0], "%Y-%m-%d").date() for h in KENYAN_HOLIDAYS]
    
    print(f"\nCurrent Date/Time: {current_datetime.strftime('%Y-%m-%d %H:%M')}")
    print(f"Holidays to skip: {len(holiday_dates)}\n")
    
    for entry in timetable_entries:
        (class_id, day_of_week, start_time, end_time, effective_from, 
         effective_to, course_code, class_name, semester, instructor_id) = entry
        
        # Parse dates
        start_date = datetime.strptime(effective_from, "%Y-%m-%d")
        end_date = datetime.strptime(effective_to, "%Y-%m-%d")
        
        # Find all occurrences of this day in the semester
        current = start_date
        
        # Move to first occurrence of the day
        while current.weekday() != (day_of_week - 1) % 7:
            current += timedelta(days=1)
        
        sessions_for_class = []
        status_counts = {
            'scheduled': 0,
            'ongoing': 0,
            'completed': 0,
            'cancelled': 0,
            'missed': 0,
            'dismissed': 0
        }
        
        # Generate sessions for each occurrence
        while current <= end_date:
            # Skip if holiday
            if current.date() not in holiday_dates:
                # Determine realistic session status using date AND time
                status = determine_session_status(current.date(), start_time, end_time, current_datetime)
                status_counts[status] += 1
                
                session = {
                    'class_id': class_id,
                    'date': format_date_for_db(current),
                    'start_time': start_time,
                    'end_time': end_time,
                    'status': status,
                    'created_by': instructor_id,  # Now uses the actual assigned instructor
                    'created_at': format_datetime_for_db(datetime.now()),
                    'updated_at': format_datetime_for_db(datetime.now()),
                    'attendance_count': 0,
                    'total_students': 0,  # Will be updated when students are added
                    'session_notes': generate_session_notes(status) if status in ['cancelled', 'dismissed', 'missed'] else None
                }
                
                sessions_for_class.append(session)
                session_data.append(session)
            
            # Move to next week
            current += timedelta(weeks=1)
        
        day_name = DAYS_OF_WEEK[day_of_week]
        
        # Create status summary string
        status_summary = ", ".join([f"{status}: {count}" for status, count in status_counts.items() if count > 0])
        
        print(f"✓ {class_id} - {class_name}")
        print(f"  Instructor: {instructor_id}")
        print(f"  {day_name} {start_time}-{end_time}: {len(sessions_for_class)} sessions")
        print(f"  Status breakdown: {status_summary}\n")
    
    # Insert into database
    cursor.executemany("""
        INSERT INTO class_sessions 
        (class_id, date, start_time, end_time, status, created_by, 
         created_at, updated_at, attendance_count, total_students, session_notes)
        VALUES (:class_id, :date, :start_time, :end_time, :status, :created_by,
                :created_at, :updated_at, :attendance_count, :total_students, :session_notes)
    """, session_data)
    
    conn.commit()
    
    # Print comprehensive summary
    print(f"\n{'=' * 50}")
    print("SESSION GENERATION SUMMARY")
    print(f"{'=' * 50}")
    
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM class_sessions
        GROUP BY status
        ORDER BY 
            CASE status
                WHEN 'completed' THEN 1
                WHEN 'scheduled' THEN 2
                WHEN 'ongoing' THEN 3
                WHEN 'dismissed' THEN 4
                WHEN 'cancelled' THEN 5
                WHEN 'missed' THEN 6
            END
    """)
    
    status_summary = cursor.fetchall()
    total_sessions = sum(count for _, count in status_summary)
    
    print(f"\nTotal Sessions: {total_sessions}")
    print(f"\nStatus Distribution:")
    for status, count in status_summary:
        percentage = (count / total_sessions * 100) if total_sessions > 0 else 0
        print(f"  {status.capitalize():12} : {count:4} ({percentage:5.1f}%)")
    
    # Sessions by course
    cursor.execute("""
        SELECT c.course_code, COUNT(*) as session_count,
               SUM(CASE WHEN cs.status = 'completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN cs.status = 'scheduled' THEN 1 ELSE 0 END) as scheduled
        FROM class_sessions cs
        JOIN classes c ON c.class_id = cs.class_id
        GROUP BY c.course_code
        ORDER BY c.course_code
    """)
    
    course_summary = cursor.fetchall()
    print(f"\nSessions by Course:")
    for course_code, total, completed, scheduled in course_summary:
        print(f"  {course_code}: {total} sessions ({completed} completed, {scheduled} scheduled)")
    
    # Sessions by instructor
    cursor.execute("""
        SELECT i.instructor_id, i.instructor_name, COUNT(*) as session_count
        FROM class_sessions cs
        JOIN instructors i ON i.instructor_id = cs.created_by
        GROUP BY i.instructor_id, i.instructor_name
        ORDER BY session_count DESC
    """)
    
    instructor_summary = cursor.fetchall()
    print(f"\nSessions by Instructor:")
    for instructor_id, instructor_name, session_count in instructor_summary:
        print(f"  {instructor_id} ({instructor_name}): {session_count} sessions")
    
    conn.close()
    
    print(f"\n✓ Successfully generated {len(session_data)} class sessions")
    return session_data

def generate_session_notes(status):
    """Generate realistic session notes based on status"""
    notes_templates = {
        'cancelled': [
            "Class cancelled due to instructor unavailability",
            "Cancelled - Public holiday observed",
            "Cancelled due to facility maintenance",
            "Administrative cancellation - Exam period",
            "Cancelled - Department meeting scheduled"
        ],
        'dismissed': [
            "Class dismissed early - technical issues",
            "Session dismissed - insufficient attendance",
            "Dismissed early due to power outage",
            "Class dismissed - emergency situation",
            "Dismissed early - instructor emergency"
        ],
        'missed': [
            "Instructor no-show - unexcused absence",
            "No instructor available",
            "Session missed - communication error",
            "Missed due to scheduling conflict",
            "Instructor absence - not rescheduled"
        ]
    }
    
    return random.choice(notes_templates.get(status, []))

if __name__ == "__main__":
    generate_sessions_from_timetable()