"""
Faker Script: Class Sessions
Generates class sessions based on timetables for the current semester
Run this AFTER faker_classes.py
"""

import sqlite3
import random
from datetime import datetime, date, timedelta
from faker.faker_config import (
    CURRENT_SEMESTER, get_date_range_for_semester,
    get_weekdays_in_range, is_holiday, is_weekend,
    DAY_NAMES, CURRENT_YEAR
)

# Constants
DATABASE_PATH = "attendance.db"  # Update this to your actual database path

# Session statuses with realistic distribution
# Note: For past sessions, 'scheduled' is not an option
# Distribution for past sessions: completed (78%), cancelled (11%), dismissed (11%)
SESSION_STATUSES = {
    'completed': 0.70,    # 70% completed (past only)
    'scheduled': 0.20,    # 20% scheduled (future/today only)
    'cancelled': 0.05,    # 5% cancelled (past only)
    'dismissed': 0.05     # 5% dismissed (past only)
}

def create_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def clear_existing_sessions(conn):
    """Clear existing class sessions"""
    print("\n🗑️  Clearing existing session data...")
    
    try:
        cursor = conn.cursor()
        
        # Delete sessions and related data
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM session_dismissals")
        cursor.execute("DELETE FROM class_sessions")
        
        conn.commit()
        print("✅ Existing session data cleared")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Error clearing sessions: {e}")
        return False

def get_timetables_for_semester(conn, semester):
    """Get all active timetables for classes in the current semester"""
    cursor = conn.cursor()
    
    # Parse semester to get year (e.g., "2.1" -> year 2)
    year = int(semester.split('.')[0])
    
    cursor.execute("""
        SELECT t.*, c.class_id, c.class_name, c.course_code, c.year, c.semester
        FROM timetable t
        JOIN classes c ON t.class_id = c.class_id
        WHERE c.semester = ? AND t.is_active = 1
        ORDER BY c.class_id, t.day_of_week, t.start_time
    """, (semester,))
    
    return cursor.fetchall()

def get_class_instructor(conn, class_id):
    """Get a random instructor assigned to this class"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT instructor_id 
        FROM class_instructors 
        WHERE class_id = ?
    """, (class_id,))
    
    instructors = cursor.fetchall()
    
    if instructors:
        return random.choice(instructors)['instructor_id']
    return None

def get_students_in_class(conn, class_id, course_code):
    """Get count of students who could attend this class"""
    cursor = conn.cursor()
    
    # Get class details
    cursor.execute("""
        SELECT year, semester FROM classes WHERE class_id = ?
    """, (class_id,))
    
    class_info = cursor.fetchone()
    if not class_info:
        return 0
    
    # Count students in this course, year, and semester
    cursor.execute("""
        SELECT COUNT(DISTINCT s.student_id) as count
        FROM students s
        WHERE s.course = ? 
        AND s.year_of_study = ?
        AND s.current_semester = ?
        AND s.is_active = 1
    """, (course_code, class_info['year'], class_info['semester']))
    
    result = cursor.fetchone()
    return result['count'] if result else 0

def generate_sessions_for_timetable(conn, timetable, start_date, end_date):
    """Generate sessions for a specific timetable entry within date range"""
    cursor = conn.cursor()
    sessions = []
    
    class_id = timetable['class_id']
    day_of_week = timetable['day_of_week']
    start_time = timetable['start_time']
    end_time = timetable['end_time']
    
    # Get instructor for this class
    instructor_id = get_class_instructor(conn, class_id)
    if not instructor_id:
        print(f"  ⚠️  No instructor found for class {class_id}")
        return sessions
    
    # Get student count for this class
    total_students = get_students_in_class(conn, class_id, timetable['course_code'])
    
    # Find all dates that match this day of week in the date range
    current_date = start_date
    while current_date <= end_date:
        # Check if this date matches the timetable's day of week
        # Python: Monday=0, Sunday=6; Our system: Sunday=0, Monday=1
        python_weekday = current_date.weekday()
        our_weekday = (python_weekday + 1) % 7
        
        if our_weekday == day_of_week:
            # Skip if it's a holiday
            if is_holiday(current_date):
                print(f"  ⏭️  Skipping {current_date} (holiday) for {timetable['class_name']}")
                current_date += timedelta(days=1)
                continue
            
            # Determine session status based on date
            today = date.today()
            
            if current_date > today:
                # Future sessions can ONLY be scheduled
                status = 'scheduled'
                attendance_count = 0
            elif current_date == today:
                # Today's sessions can be scheduled or ongoing
                status = 'scheduled'
                attendance_count = 0
            else:
                # Past sessions - CANNOT be scheduled, must have a final status
                # Recalculate weights excluding 'scheduled' status
                past_statuses = {
                    'completed': 0.778,  # 70 / (70+5+5) = 0.778
                    'cancelled': 0.111,  # 5 / 90 = 0.056 -> adjusted
                    'dismissed': 0.111   # 5 / 90 = 0.056 -> adjusted
                }
                
                rand = random.random()
                if rand < past_statuses['completed']:
                    status = 'completed'
                    # Attendance between 60-95% for completed sessions
                    if total_students > 0:
                        attendance_rate = random.uniform(0.60, 0.95)
                        attendance_count = int(total_students * attendance_rate)
                    else:
                        attendance_count = 0
                elif rand < past_statuses['completed'] + past_statuses['cancelled']:
                    status = 'cancelled'
                    attendance_count = 0
                else:
                    status = 'dismissed'
                    attendance_count = 0
            
            # Insert session
            try:
                cursor.execute("""
                    INSERT INTO class_sessions 
                    (class_id, date, start_time, end_time, status, created_by, 
                     created_at, updated_at, attendance_count, total_students)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    class_id,
                    current_date.strftime('%Y-%m-%d'),
                    start_time,
                    end_time,
                    status,
                    instructor_id,
                    datetime.utcnow(),
                    datetime.utcnow(),
                    attendance_count,
                    total_students
                ))
                
                session_id = cursor.lastrowid
                
                sessions.append({
                    'session_id': session_id,
                    'class_id': class_id,
                    'date': current_date,
                    'status': status,
                    'attendance_count': attendance_count,
                    'total_students': total_students
                })
                
            except sqlite3.Error as e:
                print(f"  ❌ Error inserting session: {e}")
        
        current_date += timedelta(days=1)
    
    return sessions

def generate_sessions(conn):
    """Generate sessions for all timetables in current semester"""
    print(f"\n📅 Generating Sessions for Semester {CURRENT_SEMESTER}...")
    
    # Get date range for current semester
    start_date, end_date = get_date_range_for_semester(CURRENT_SEMESTER, CURRENT_YEAR)
    
    if not start_date or not end_date:
        print(f"❌ Could not determine date range for semester {CURRENT_SEMESTER}")
        return []
    
    print(f"  Date Range: {start_date} to {end_date}")
    
    # Get all timetables for this semester
    timetables = get_timetables_for_semester(conn, CURRENT_SEMESTER)
    
    if not timetables:
        print(f"  ⚠️  No timetables found for semester {CURRENT_SEMESTER}")
        return []
    
    print(f"  Found {len(timetables)} timetable entries")
    
    all_sessions = []
    
    for timetable in timetables:
        class_name = timetable['class_name'][:40]
        day_name = DAY_NAMES[timetable['day_of_week']]
        
        print(f"\n  Processing: {class_name}... ({day_name} {timetable['start_time']}-{timetable['end_time']})")
        
        sessions = generate_sessions_for_timetable(conn, timetable, start_date, end_date)
        all_sessions.extend(sessions)
        
        print(f"    ✓ Generated {len(sessions)} sessions")
    
    conn.commit()
    print(f"\n✅ Total sessions generated: {len(all_sessions)}")
    return all_sessions

def generate_session_dismissals(conn, sessions):
    """Generate dismissal records for dismissed sessions"""
    print("\n📝 Generating Session Dismissals...")
    
    cursor = conn.cursor()
    dismissals = []
    
    dismissed_sessions = [s for s in sessions if s['status'] == 'dismissed']
    
    if not dismissed_sessions:
        print("  No dismissed sessions to process")
        return dismissals
    
    dismissal_reasons = [
        "Instructor unavailable due to emergency",
        "Classroom not available",
        "Technical difficulties with equipment",
        "Instructor illness",
        "University event conflict",
        "Insufficient student attendance",
        "Weather-related closure",
        "Power outage",
        "Facility maintenance"
    ]
    
    for session in dismissed_sessions:
        # Get instructor for this session
        cursor.execute("""
            SELECT created_by FROM class_sessions WHERE session_id = ?
        """, (session['session_id'],))
        
        result = cursor.fetchone()
        if not result:
            continue
        
        instructor_id = result['created_by']
        reason = random.choice(dismissal_reasons)
        
        # 30% chance of rescheduling
        if random.random() < 0.30:
            # Reschedule to a future date (1-7 days later)
            original_date = session['date']
            days_ahead = random.randint(1, 7)
            rescheduled_date = original_date + timedelta(days=days_ahead)
            
            cursor.execute("""
                SELECT start_time, end_time FROM class_sessions WHERE session_id = ?
            """, (session['session_id'],))
            time_info = cursor.fetchone()
            
            status = 'rescheduled'
            rescheduled_to = rescheduled_date.strftime('%Y-%m-%d')
            rescheduled_time = time_info['start_time'] if time_info else None
        else:
            status = 'dismissed'
            rescheduled_to = None
            rescheduled_time = None
        
        try:
            cursor.execute("""
                INSERT INTO session_dismissals 
                (session_id, instructor_id, reason, dismissal_time, 
                 rescheduled_to, rescheduled_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session['session_id'],
                instructor_id,
                reason,
                datetime.utcnow(),
                rescheduled_to,
                rescheduled_time,
                status
            ))
            
            dismissals.append({
                'session_id': session['session_id'],
                'reason': reason,
                'status': status
            })
            
        except sqlite3.Error as e:
            print(f"  ❌ Error inserting dismissal: {e}")
    
    conn.commit()
    print(f"✅ {len(dismissals)} session dismissals created")
    return dismissals

def print_session_statistics(conn):
    """Print session statistics"""
    print("\n📊 Session Statistics:")
    print("-" * 70)
    
    cursor = conn.cursor()
    
    # Total sessions
    cursor.execute("SELECT COUNT(*) as count FROM class_sessions")
    total = cursor.fetchone()['count']
    print(f"  Total Sessions: {total}")
    
    # Sessions by status
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM class_sessions 
        GROUP BY status
        ORDER BY count DESC
    """)
    print("\n  Sessions by Status:")
    for row in cursor.fetchall():
        print(f"    {row['status'].capitalize()}: {row['count']}")
    
    # Sessions by date range
    cursor.execute("""
        SELECT 
            MIN(date) as earliest,
            MAX(date) as latest
        FROM class_sessions
    """)
    date_range = cursor.fetchone()
    print(f"\n  Date Range: {date_range['earliest']} to {date_range['latest']}")
    
    # Average attendance for completed sessions
    cursor.execute("""
        SELECT 
            AVG(CAST(attendance_count AS REAL) / NULLIF(total_students, 0) * 100) as avg_rate
        FROM class_sessions
        WHERE status = 'completed' AND total_students > 0
    """)
    avg_attendance = cursor.fetchone()['avg_rate']
    if avg_attendance:
        print(f"  Average Attendance Rate (Completed): {avg_attendance:.1f}%")
    
    # Sessions per class (top 5)
    cursor.execute("""
        SELECT c.class_name, COUNT(cs.session_id) as session_count
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        GROUP BY cs.class_id
        ORDER BY session_count DESC
        LIMIT 5
    """)
    print("\n  Top 5 Classes by Session Count:")
    for row in cursor.fetchall():
        class_name = row['class_name'][:50]
        print(f"    {class_name}: {row['session_count']} sessions")
    
    print("-" * 70)

def print_sample_sessions(conn):
    """Print sample sessions"""
    print("\n📋 Sample Sessions (First 10):")
    print("-" * 90)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            cs.session_id,
            c.class_name,
            cs.date,
            cs.start_time,
            cs.end_time,
            cs.status,
            cs.attendance_count,
            cs.total_students
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        ORDER BY cs.date DESC, cs.start_time
        LIMIT 10
    """)
    
    print(f"{'ID':<6} {'Class':<35} {'Date':<12} {'Time':<13} {'Status':<10} {'Attend':<8}")
    print("-" * 90)
    
    for row in cursor.fetchall():
        class_name = row['class_name'][:33]
        attendance_info = f"{row['attendance_count']}/{row['total_students']}" if row['total_students'] > 0 else "N/A"
        time_info = f"{row['start_time']}-{row['end_time']}"
        
        print(f"{row['session_id']:<6} {class_name:<35} {row['date']:<12} {time_info:<13} {row['status']:<10} {attendance_info:<8}")
    
    print("-" * 90)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT: CLASS SESSIONS")
    print("=" * 70)
    
    conn = create_connection()
    if conn is None:
        print("❌ Failed to connect to database")
        return
    
    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Verify required data exists
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM classes")
        class_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM timetable")
        timetable_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM instructors")
        instructor_count = cursor.fetchone()['count']
        
        if class_count == 0 or timetable_count == 0 or instructor_count == 0:
            print("\n❌ ERROR: Please run faker_classes.py first!")
            print(f"   Classes: {class_count}, Timetables: {timetable_count}, Instructors: {instructor_count}")
            return
        
        print(f"\n✓ Found {class_count} classes, {timetable_count} timetables, {instructor_count} instructors")
        
        # Clear existing sessions
        if not clear_existing_sessions(conn):
            return
        
        # Generate sessions
        sessions = generate_sessions(conn)
        
        if not sessions:
            print("\n⚠️  No sessions were generated")
            return
        
        # Generate dismissals
        dismissals = generate_session_dismissals(conn, sessions)
        
        # Print statistics
        print_session_statistics(conn)
        
        # Print samples
        print_sample_sessions(conn)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ SESSION GENERATION COMPLETE!")
        print("=" * 70)
        print(f"📅 Total Sessions: {len(sessions)}")
        print(f"📝 Session Dismissals: {len(dismissals)}")
        print(f"📚 Current Semester: {CURRENT_SEMESTER}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()