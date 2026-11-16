"""
Faker script to generate realistic attendance data
Uses student_courses and class_courses tables for enrollment
"""

import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / 'attendance.db'

# Attendance configuration
ATTENDANCE_CONFIG = {
    'overall_attendance_rate': 0.82,
    'late_rate': 0.08,
    'excused_rate': 0.05,
    'excellent_students': 0.20,
    'good_students': 0.45,
    'average_students': 0.25,
    'poor_students': 0.10,
    'morning_absence_multiplier': 1.3,
    'friday_absence_multiplier': 1.2,
    'face_recognition_rate': 0.75,
    'manual_rate': 0.20,
    'api_rate': 0.05,
    'high_confidence_rate': 0.85,
    'medium_confidence_rate': 0.12,
    'low_confidence_rate': 0.03,
}

# Student attendance profiles
STUDENT_PROFILES = {
    'excellent': {'min': 0.95, 'max': 1.0, 'late_chance': 0.02},
    'good': {'min': 0.80, 'max': 0.95, 'late_chance': 0.08},
    'average': {'min': 0.65, 'max': 0.80, 'late_chance': 0.12},
    'poor': {'min': 0.30, 'max': 0.65, 'late_chance': 0.15}
}


def assign_student_profile():
    """Assign a random attendance profile to a student"""
    rand = random.random()
    if rand < ATTENDANCE_CONFIG['excellent_students']:
        return 'excellent'
    elif rand < (ATTENDANCE_CONFIG['excellent_students'] + ATTENDANCE_CONFIG['good_students']):
        return 'good'
    elif rand < (ATTENDANCE_CONFIG['excellent_students'] + ATTENDANCE_CONFIG['good_students'] + 
                 ATTENDANCE_CONFIG['average_students']):
        return 'average'
    else:
        return 'poor'


def get_attendance_probability(student_profile, session_datetime, session_day_of_week):
    """Calculate attendance probability based on various factors"""
    profile = STUDENT_PROFILES[student_profile]
    base_probability = random.uniform(profile['min'], profile['max'])
    
    # Early morning penalty (before 9 AM)
    if session_datetime.hour < 9:
        base_probability *= (1 / ATTENDANCE_CONFIG['morning_absence_multiplier'])
    
    # Friday penalty
    if session_day_of_week == 4:
        base_probability *= (1 / ATTENDANCE_CONFIG['friday_absence_multiplier'])
    
    # Random variation
    base_probability *= random.uniform(0.95, 1.05)
    
    return min(1.0, base_probability)


def generate_marking_method():
    """Generate realistic marking method"""
    rand = random.random()
    if rand < ATTENDANCE_CONFIG['face_recognition_rate']:
        return 'face_recognition'
    elif rand < (ATTENDANCE_CONFIG['face_recognition_rate'] + ATTENDANCE_CONFIG['manual_rate']):
        return 'manual'
    else:
        return 'api'


def generate_confidence_score(method):
    """Generate confidence score for face recognition"""
    if method != 'face_recognition':
        return None
    
    rand = random.random()
    if rand < ATTENDANCE_CONFIG['high_confidence_rate']:
        return round(random.uniform(0.80, 0.99), 2)
    elif rand < (ATTENDANCE_CONFIG['high_confidence_rate'] + ATTENDANCE_CONFIG['medium_confidence_rate']):
        return round(random.uniform(0.60, 0.80), 2)
    else:
        return round(random.uniform(0.45, 0.60), 2)


def generate_attendance_time(session_date, start_time, status):
    """Generate realistic attendance marking time"""
    session_datetime = datetime.strptime(f"{session_date} {start_time}", "%Y-%m-%d %H:%M")
    
    if status == 'Present':
        minutes_offset = random.randint(0, 10)
        seconds_offset = random.randint(0, 59)
    elif status == 'Late':
        minutes_offset = random.randint(10, 30)
        seconds_offset = random.randint(0, 59)
    elif status == 'Excused':
        minutes_offset = random.randint(0, 45)
        seconds_offset = random.randint(0, 59)
    else:  # Absent
        minutes_offset = random.randint(30, 90)
        seconds_offset = random.randint(0, 59)
    
    timestamp = session_datetime + timedelta(minutes=minutes_offset, seconds=seconds_offset)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def generate_notes(status, method):
    """Generate realistic notes for attendance records"""
    notes_templates = {
        'Late': [
            'Arrived late due to traffic',
            'Previous class ran over',
            'Technical issues with login',
            'Had to submit assignment',
            None, None, None,
        ],
        'Excused': [
            'Medical appointment',
            'Family emergency',
            'University-approved event',
            'Documented illness',
            'Official university business',
            'Medical certificate submitted',
            'Prior permission granted',
        ],
        'Absent': [None, None, None, None, 'No response to follow-up']
    }
    
    if status in notes_templates:
        return random.choice(notes_templates[status])
    return None


def diagnose_database(conn):
    """Diagnose database structure and data"""
    cursor = conn.cursor()
    
    print("\n🔍 DATABASE DIAGNOSTICS")
    print("=" * 60)
    
    # Check students
    cursor.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
    total_students = cursor.fetchone()[0]
    print(f"✅ Active students: {total_students}")
    
    # Check classes
    cursor.execute("SELECT COUNT(*) FROM classes WHERE is_active = 1")
    total_classes = cursor.fetchone()[0]
    print(f"✅ Active classes: {total_classes}")
    
    # Check completed sessions
    cursor.execute("SELECT COUNT(*) FROM class_sessions WHERE status = 'completed'")
    total_sessions = cursor.fetchone()[0]
    print(f"✅ Completed sessions: {total_sessions}")
    
    # Check student_courses
    cursor.execute("SELECT COUNT(*) FROM student_courses WHERE status = 'Active'")
    active_enrollments = cursor.fetchone()[0]
    print(f"📊 Active student enrollments (student_courses): {active_enrollments}")
    
    # Check class_courses
    cursor.execute("SELECT COUNT(*) FROM class_courses")
    class_course_links = cursor.fetchone()[0]
    print(f"📊 Class-course links (class_courses): {class_course_links}")
    
    if active_enrollments == 0:
        print("\n⚠️  WARNING: No active student enrollments found in student_courses!")
        print("   Please populate student_courses table first.")
        return False
    
    if class_course_links == 0:
        print("\n⚠️  WARNING: No class-course links found in class_courses!")
        print("   Please populate class_courses table first.")
        return False
    
    # Test sample session
    cursor.execute("""
        SELECT cs.session_id, cs.class_id, c.class_name, cc.course_code
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        LEFT JOIN class_courses cc ON cc.class_id = cs.class_id
        WHERE cs.status = 'completed'
        LIMIT 1
    """)
    
    sample = cursor.fetchone()
    if sample:
        session_id, class_id, class_name, course_code = sample
        print(f"\n🧪 Testing sample session {session_id}:")
        print(f"   Class: {class_name} (ID: {class_id})")
        print(f"   Course: {course_code if course_code else 'NOT LINKED'}")
        
        if not course_code:
            print("\n❌ PROBLEM: Class is not linked to any course in class_courses!")
            return False
        
        # Count students for this class
        cursor.execute("""
            SELECT COUNT(DISTINCT s.student_id)
            FROM students s
            JOIN student_courses sc ON s.student_id = sc.student_id
            JOIN class_courses cc ON sc.course_code = cc.course_code
            WHERE cc.class_id = ? AND sc.status = 'Active' AND s.is_active = 1
        """, (class_id,))
        
        student_count = cursor.fetchone()[0]
        print(f"   Students found via join: {student_count}")
        
        if student_count == 0:
            print("\n❌ PROBLEM: No students found for this class!")
            print("   Possible issues:")
            print("   - Students not enrolled in this course in student_courses")
            print("   - Course codes don't match between tables")
            return False
        
        print("   ✅ Test passed - students found successfully")
    
    print("=" * 60)
    return True


def get_enrolled_students(conn, class_id):
    """Get all enrolled students for a class using student_courses and class_courses"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT s.student_id
        FROM students s
        JOIN student_courses sc ON s.student_id = sc.student_id
        JOIN class_courses cc ON sc.course_code = cc.course_code
        WHERE cc.class_id = ? 
        AND sc.status = 'Active' 
        AND s.is_active = 1
    """, (class_id,))
    
    return [row[0] for row in cursor.fetchall()]


def create_attendance_records(conn):
    """Generate attendance records for all completed sessions"""
    cursor = conn.cursor()
    
    print("\n🎯 GENERATING ATTENDANCE RECORDS")
    print("=" * 60)
    
    # Get all completed sessions
    cursor.execute("""
        SELECT 
            cs.session_id,
            cs.class_id,
            cs.date,
            cs.start_time,
            cs.end_time,
            cs.created_by,
            c.class_name
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        WHERE cs.status = 'completed'
        ORDER BY cs.date, cs.start_time
    """)
    
    completed_sessions = cursor.fetchall()
    total_sessions = len(completed_sessions)
    
    print(f"📊 Processing {total_sessions} completed sessions\n")
    
    if total_sessions == 0:
        print("⚠️  No completed sessions found!")
        return
    
    # Initialize statistics
    total_records = 0
    sessions_with_students = 0
    sessions_without_students = 0
    status_counts = {'Present': 0, 'Absent': 0, 'Late': 0, 'Excused': 0}
    method_counts = {'face_recognition': 0, 'manual': 0, 'api': 0}
    
    # Assign consistent attendance profiles to all students
    cursor.execute("SELECT student_id FROM students WHERE is_active = 1")
    all_students = [row[0] for row in cursor.fetchall()]
    student_profiles = {student_id: assign_student_profile() for student_id in all_students}
    
    print(f"👥 Assigned attendance profiles to {len(all_students)} students:")
    profile_dist = {}
    for profile in student_profiles.values():
        profile_dist[profile] = profile_dist.get(profile, 0) + 1
    
    for profile in sorted(profile_dist.keys()):
        count = profile_dist[profile]
        pct = (count / len(all_students) * 100) if all_students else 0
        print(f"   {profile.capitalize()}: {count} ({pct:.1f}%)")
    print()
    
    # Process each session
    for idx, session in enumerate(completed_sessions, 1):
        session_id, class_id, date, start_time, end_time, created_by, class_name = session
        
        # Get enrolled students
        enrolled_students = get_enrolled_students(conn, class_id)
        
        if not enrolled_students:
            sessions_without_students += 1
            print(f"⚠️  [{idx}/{total_sessions}] Session {session_id} - {class_name}: No students")
            continue
        
        sessions_with_students += 1
        session_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        day_of_week = session_datetime.weekday()
        
        session_records = []
        session_status = {'Present': 0, 'Absent': 0, 'Late': 0, 'Excused': 0}
        
        # Generate attendance for each student
        for student_id in enrolled_students:
            profile = student_profiles.get(student_id, 'average')
            attendance_prob = get_attendance_probability(profile, session_datetime, day_of_week)
            attends = random.random() < attendance_prob
            
            if attends:
                is_late = random.random() < STUDENT_PROFILES[profile]['late_chance']
                status = 'Late' if is_late else 'Present'
            else:
                is_excused = random.random() < ATTENDANCE_CONFIG['excused_rate']
                status = 'Excused' if is_excused else 'Absent'
            
            method = generate_marking_method()
            confidence_score = generate_confidence_score(method)
            timestamp = generate_attendance_time(date, start_time, status)
            notes = generate_notes(status, method)
            
            if method == 'manual':
                marked_by = created_by
            elif method == 'face_recognition':
                marked_by = created_by if random.random() < 0.9 else None
            else:
                marked_by = None
            
            session_records.append((
                student_id, session_id, timestamp, status,
                marked_by, method, confidence_score, notes
            ))
            
            session_status[status] += 1
            status_counts[status] += 1
            method_counts[method] += 1
        
        # Insert attendance records
        cursor.executemany("""
            INSERT INTO attendance (
                student_id, session_id, timestamp, status,
                marked_by, method, confidence_score, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, session_records)
        
        total_records += len(session_records)
        
        # Update session statistics
        attendance_count = session_status['Present'] + session_status['Late']
        total_students = len(enrolled_students)
        
        cursor.execute("""
            UPDATE class_sessions 
            SET attendance_count = ?, total_students = ?
            WHERE session_id = ?
        """, (attendance_count, total_students, session_id))
        
        # Progress update
        attendance_rate = (attendance_count / total_students * 100) if total_students > 0 else 0
        print(f"✅ [{idx}/{total_sessions}] {class_name} - {date} {start_time}")
        print(f"   {total_students} students | Present: {session_status['Present']} | "
              f"Late: {session_status['Late']} | Absent: {session_status['Absent']} | "
              f"Excused: {session_status['Excused']} | Rate: {attendance_rate:.1f}%")
    
    conn.commit()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ GENERATION COMPLETE")
    print("=" * 60)
    print(f"Sessions processed: {total_sessions}")
    print(f"  - With students: {sessions_with_students}")
    print(f"  - Without students: {sessions_without_students}")
    print(f"Total records created: {total_records:,}\n")
    
    if total_records > 0:
        print("📊 Status Distribution:")
        total_status = sum(status_counts.values())
        for status in sorted(status_counts.keys()):
            count = status_counts[status]
            pct = (count / total_status * 100) if total_status > 0 else 0
            print(f"   {status}: {count:,} ({pct:.1f}%)")
        
        overall_rate = ((status_counts['Present'] + status_counts['Late']) / total_status * 100) if total_status > 0 else 0
        print(f"\n   Overall Attendance Rate: {overall_rate:.1f}%\n")
        
        print("🔧 Marking Methods:")
        total_methods = sum(method_counts.values())
        for method in sorted(method_counts.keys()):
            count = method_counts[method]
            pct = (count / total_methods * 100) if total_methods > 0 else 0
            print(f"   {method}: {count:,} ({pct:.1f}%)")
    
    print("=" * 60)


def verify_data(conn):
    """Verify the generated attendance data"""
    cursor = conn.cursor()
    
    print("\n🔍 VERIFICATION")
    print("=" * 60)
    
    # Check duplicates
    cursor.execute("""
        SELECT student_id, session_id, COUNT(*) as cnt
        FROM attendance
        GROUP BY student_id, session_id
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} duplicate records!")
    else:
        print("✅ No duplicate records")
    
    # Overall stats
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as records,
            AVG(CASE WHEN confidence_score IS NOT NULL THEN confidence_score END) as avg_conf
        FROM attendance
    """)
    stats = cursor.fetchone()
    
    print(f"✅ Sessions with attendance: {stats[0]}")
    print(f"✅ Total attendance records: {stats[1]:,}")
    if stats[2]:
        print(f"✅ Avg face recognition confidence: {stats[2]:.2f}")
    
    print("=" * 60)


def main():
    """Main execution"""
    print("\n" + "=" * 60)
    print("🎯 ATTENDANCE DATA FAKER")
    print("   Using student_courses & class_courses tables")
    print("=" * 60)
    
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Run diagnostics
        if not diagnose_database(conn):
            print("\n❌ Diagnostics failed. Please fix the issues above.")
            return
        
        # Check existing data
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM attendance")
        existing = cursor.fetchone()[0]
        
        if existing > 0:
            response = input(f"\n⚠️  Found {existing:,} existing records. Delete? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Aborted")
                return
            cursor.execute("DELETE FROM attendance")
            conn.commit()
            print(f"✅ Deleted {existing:,} records\n")
        
        # Generate data
        create_attendance_records(conn)
        
        # Verify
        verify_data(conn)
        
        conn.close()
        print("\n✅ Complete!\n")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()