"""
Faker Script: Attendance Records
Generates realistic attendance records for completed sessions
Run this AFTER faker_sessions.py and after students have been created
"""

import sqlite3
import random
from datetime import datetime, date, time, timedelta

# Constants
DATABASE_PATH = "attendance.db"  # Update this to your actual database path

# Attendance distribution (realistic percentages)
# Note: We never allow 100% attendance to be realistic
ATTENDANCE_PATTERNS = {
    'high': {  # 75-95% attendance
        'min': 0.75,
        'max': 0.95,
        'weight': 0.60  # 60% of sessions have high attendance
    },
    'medium': {  # 60-75% attendance
        'min': 0.60,
        'max': 0.75,
        'weight': 0.30  # 30% of sessions have medium attendance
    },
    'low': {  # 40-60% attendance
        'min': 0.40,
        'max': 0.60,
        'weight': 0.10  # 10% of sessions have low attendance
    }
}

# Attendance status distribution for students who attend
ATTENDANCE_STATUS_WEIGHTS = {
    'Present': 0.85,  # 85% on time
    'Late': 0.15      # 15% late
}

# Face recognition confidence scores (realistic ranges)
CONFIDENCE_RANGES = {
    'high': (0.85, 0.98),    # 85-98% confidence
    'medium': (0.70, 0.85),  # 70-85% confidence
}

def create_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def clear_existing_attendance(conn):
    """Clear existing attendance records"""
    print("\n🗑️  Clearing existing attendance data...")
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attendance")
        conn.commit()
        print("✅ Existing attendance data cleared")
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Error clearing attendance: {e}")
        return False

def get_eligible_sessions(conn):
    """Get sessions that can have attendance (completed sessions in the past)"""
    cursor = conn.cursor()
    
    today = date.today().strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT 
            cs.session_id,
            cs.class_id,
            cs.date,
            cs.start_time,
            cs.end_time,
            cs.status,
            cs.created_by,
            c.course_code,
            c.year,
            c.semester,
            c.class_name
        FROM class_sessions cs
        JOIN classes c ON cs.class_id = c.class_id
        WHERE cs.status = 'completed'
        AND cs.date < ?
        ORDER BY cs.date, cs.start_time
    """, (today,))
    
    return cursor.fetchall()

def get_students_for_session(conn, session):
    """Get all students eligible to attend a session"""
    cursor = conn.cursor()
    
    # Get students in the same course, year, and semester
    cursor.execute("""
        SELECT 
            s.student_id,
            s.fname,
            s.lname,
            s.face_encoding
        FROM students s
        WHERE s.course = ?
        AND s.year_of_study = ?
        AND s.current_semester = ?
        AND s.is_active = 1
        AND s.face_encoding IS NOT NULL
    """, (session['course_code'], session['year'], session['semester']))
    
    return cursor.fetchall()

def determine_attendance_pattern():
    """Determine which attendance pattern to use for a session"""
    rand = random.random()
    cumulative = 0
    
    for pattern_name, pattern_info in ATTENDANCE_PATTERNS.items():
        cumulative += pattern_info['weight']
        if rand < cumulative:
            return pattern_name, pattern_info
    
    # Fallback to high
    return 'high', ATTENDANCE_PATTERNS['high']

def generate_attendance_for_session(conn, session, students):
    """Generate attendance records for a single session"""
    if not students:
        return []
    
    cursor = conn.cursor()
    attendance_records = []
    
    # Determine attendance pattern for this session
    pattern_name, pattern_info = determine_attendance_pattern()
    
    # Calculate how many students will attend (never 100%)
    attendance_rate = random.uniform(pattern_info['min'], pattern_info['max'])
    num_attending = int(len(students) * attendance_rate)
    
    # Ensure we don't get 100% attendance even by rounding
    if num_attending == len(students) and len(students) > 1:
        num_attending -= 1
    
    # Randomly select which students attend
    attending_students = random.sample(students, num_attending)
    attending_ids = set(s['student_id'] for s in attending_students)
    
    # Generate attendance records
    for student in students:
        student_id = student['student_id']
        
        if student_id in attending_ids:
            # Student attended - determine if Present or Late
            rand = random.random()
            if rand < ATTENDANCE_STATUS_WEIGHTS['Present']:
                status = 'Present'
                # Present students: high confidence
                confidence_min, confidence_max = CONFIDENCE_RANGES['high']
            else:
                status = 'Late'
                # Late students: mix of high and medium confidence
                if random.random() < 0.7:
                    confidence_min, confidence_max = CONFIDENCE_RANGES['high']
                else:
                    confidence_min, confidence_max = CONFIDENCE_RANGES['medium']
            
            confidence_score = random.uniform(confidence_min, confidence_max)
            
            # Calculate timestamp (within session time or slightly after for late)
            session_date = datetime.strptime(session['date'], '%Y-%m-%d').date()
            session_start = datetime.strptime(session['start_time'], '%H:%M').time()
            
            if status == 'Present':
                # Arrived within first 10 minutes of class
                minutes_offset = random.randint(0, 10)
            else:  # Late
                # Arrived 11-30 minutes after start
                minutes_offset = random.randint(11, 30)
            
            timestamp = datetime.combine(session_date, session_start) + timedelta(minutes=minutes_offset)
            
            method = 'face_recognition'
            marked_by = session['created_by']
            
        else:
            # Student was absent
            status = 'Absent'
            timestamp = datetime.combine(
                datetime.strptime(session['date'], '%Y-%m-%d').date(),
                datetime.strptime(session['end_time'], '%H:%M').time()
            )
            confidence_score = None
            method = 'manual'
            marked_by = session['created_by']
        
        # Insert attendance record
        try:
            cursor.execute("""
                INSERT INTO attendance 
                (student_id, session_id, timestamp, status, marked_by, 
                 method, confidence_score, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id,
                session['session_id'],
                timestamp,
                status,
                marked_by,
                method,
                confidence_score,
                None  # notes
            ))
            
            attendance_records.append({
                'student_id': student_id,
                'session_id': session['session_id'],
                'status': status,
                'confidence_score': confidence_score
            })
            
        except sqlite3.Error as e:
            print(f"  ❌ Error inserting attendance for {student_id}: {e}")
            continue
    
    return attendance_records

def update_session_counts(conn, session_id):
    """Update attendance_count and total_students for a session"""
    cursor = conn.cursor()
    
    # Count present and late students
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM attendance
        WHERE session_id = ? AND status IN ('Present', 'Late')
    """, (session_id,))
    attendance_count = cursor.fetchone()['count']
    
    # Count total students
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM attendance
        WHERE session_id = ?
    """, (session_id,))
    total_students = cursor.fetchone()['count']
    
    # Update session
    cursor.execute("""
        UPDATE class_sessions
        SET attendance_count = ?, total_students = ?
        WHERE session_id = ?
    """, (attendance_count, total_students, session_id))

def generate_attendance(conn):
    """Generate attendance for all eligible sessions"""
    print("\n📊 Generating Attendance Records...")
    
    # Get eligible sessions (completed, past sessions only)
    sessions = get_eligible_sessions(conn)
    
    if not sessions:
        print("  ⚠️  No eligible sessions found for attendance generation")
        print("     (Need completed sessions in the past)")
        return []
    
    print(f"  Found {len(sessions)} eligible sessions")
    
    all_attendance = []
    sessions_processed = 0
    
    for session in sessions:
        # Get students for this session
        students = get_students_for_session(conn, session)
        
        if not students:
            print(f"  ⚠️  No students found for session {session['session_id']} ({session['class_name'][:40]})")
            continue
        
        # Generate attendance
        attendance = generate_attendance_for_session(conn, session, students)
        all_attendance.extend(attendance)
        
        # Update session counts
        update_session_counts(conn, session['session_id'])
        
        sessions_processed += 1
        
        if sessions_processed % 20 == 0:
            conn.commit()  # Commit in batches
            print(f"    Processed {sessions_processed}/{len(sessions)} sessions...")
    
    conn.commit()
    print(f"\n✅ Generated {len(all_attendance)} attendance records for {sessions_processed} sessions")
    return all_attendance

def print_attendance_statistics(conn):
    """Print attendance statistics"""
    print("\n📊 Attendance Statistics:")
    print("-" * 70)
    
    cursor = conn.cursor()
    
    # Total attendance records
    cursor.execute("SELECT COUNT(*) as count FROM attendance")
    total_records = cursor.fetchone()['count']
    print(f"  Total Attendance Records: {total_records}")
    
    # Records by status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM attendance
        GROUP BY status
        ORDER BY count DESC
    """)
    print("\n  Records by Status:")
    for row in cursor.fetchall():
        percentage = (row['count'] / total_records * 100) if total_records > 0 else 0
        print(f"    {row['status']}: {row['count']} ({percentage:.1f}%)")
    
    # Average attendance rate per session
    cursor.execute("""
        SELECT 
            AVG(CAST(attendance_count AS REAL) / NULLIF(total_students, 0) * 100) as avg_rate,
            MIN(CAST(attendance_count AS REAL) / NULLIF(total_students, 0) * 100) as min_rate,
            MAX(CAST(attendance_count AS REAL) / NULLIF(total_students, 0) * 100) as max_rate
        FROM class_sessions
        WHERE status = 'completed' AND total_students > 0
    """)
    rates = cursor.fetchone()
    print(f"\n  Attendance Rates (Completed Sessions):")
    print(f"    Average: {rates['avg_rate']:.1f}%")
    print(f"    Minimum: {rates['min_rate']:.1f}%")
    print(f"    Maximum: {rates['max_rate']:.1f}%")
    
    # Verify no 100% attendance sessions
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM class_sessions
        WHERE status = 'completed' 
        AND total_students > 0
        AND attendance_count = total_students
    """)
    perfect_attendance = cursor.fetchone()['count']
    if perfect_attendance > 0:
        print(f"\n  ⚠️  WARNING: {perfect_attendance} sessions have 100% attendance!")
    else:
        print(f"\n  ✅ No sessions have 100% attendance (realistic)")
    
    # Average confidence scores
    cursor.execute("""
        SELECT 
            AVG(confidence_score) as avg_confidence,
            MIN(confidence_score) as min_confidence,
            MAX(confidence_score) as max_confidence
        FROM attendance
        WHERE confidence_score IS NOT NULL
    """)
    confidence = cursor.fetchone()
    print(f"\n  Face Recognition Confidence:")
    print(f"    Average: {confidence['avg_confidence']:.2f}")
    print(f"    Range: {confidence['min_confidence']:.2f} - {confidence['max_confidence']:.2f}")
    
    # Sessions with attendance data
    cursor.execute("""
        SELECT COUNT(DISTINCT session_id) as count
        FROM attendance
    """)
    sessions_with_data = cursor.fetchone()['count']
    print(f"\n  Sessions with Attendance Data: {sessions_with_data}")
    
    # Verify no future sessions have attendance
    cursor.execute("""
        SELECT COUNT(DISTINCT a.id) as count
        FROM attendance a
        JOIN class_sessions cs ON a.session_id = cs.session_id
        WHERE cs.date > date('now')
    """)
    future_attendance = cursor.fetchone()['count']
    if future_attendance > 0:
        print(f"\n  ⚠️  WARNING: {future_attendance} future sessions have attendance data!")
    else:
        print(f"  ✅ No future sessions have attendance data")
    
    # Verify no cancelled/dismissed sessions have attendance
    cursor.execute("""
        SELECT COUNT(DISTINCT a.id) as count
        FROM attendance a
        JOIN class_sessions cs ON a.session_id = cs.session_id
        WHERE cs.status IN ('cancelled', 'dismissed')
    """)
    invalid_attendance = cursor.fetchone()['count']
    if invalid_attendance > 0:
        print(f"  ⚠️  WARNING: {invalid_attendance} cancelled/dismissed sessions have attendance!")
    else:
        print(f"  ✅ No cancelled/dismissed sessions have attendance data")
    
    print("-" * 70)

def print_sample_attendance(conn):
    """Print sample attendance records"""
    print("\n📋 Sample Attendance Records (Recent 15):")
    print("-" * 100)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.student_id,
            s.fname || ' ' || s.lname as student_name,
            c.class_name,
            cs.date,
            a.status,
            a.confidence_score,
            a.method
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        JOIN class_sessions cs ON a.session_id = cs.session_id
        JOIN classes c ON cs.class_id = c.class_id
        ORDER BY cs.date DESC, a.timestamp DESC
        LIMIT 15
    """)
    
    print(f"{'Student ID':<12} {'Name':<25} {'Class':<25} {'Date':<12} {'Status':<8} {'Conf':<6} {'Method':<10}")
    print("-" * 100)
    
    for row in cursor.fetchall():
        class_name = row['class_name'][:23]
        student_name = row['student_name'][:23]
        conf = f"{row['confidence_score']:.2f}" if row['confidence_score'] else "N/A"
        
        print(f"{row['student_id']:<12} {student_name:<25} {class_name:<25} {row['date']:<12} {row['status']:<8} {conf:<6} {row['method']:<10}")
    
    print("-" * 100)

def print_student_summary(conn):
    """Print attendance summary for sample students"""
    print("\n👥 Student Attendance Summary (Top 10 by Total Sessions):")
    print("-" * 80)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            s.student_id,
            s.fname || ' ' || s.lname as student_name,
            COUNT(a.id) as total_sessions,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
            ROUND(SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) * 100.0 / COUNT(a.id), 1) as attendance_rate
        FROM students s
        JOIN attendance a ON s.student_id = a.student_id
        GROUP BY s.student_id
        ORDER BY total_sessions DESC
        LIMIT 10
    """)
    
    print(f"{'Student ID':<12} {'Name':<25} {'Total':<7} {'Present':<8} {'Late':<6} {'Absent':<8} {'Rate':<6}")
    print("-" * 80)
    
    for row in cursor.fetchall():
        student_name = row['student_name'][:23]
        print(f"{row['student_id']:<12} {student_name:<25} {row['total_sessions']:<7} {row['present_count']:<8} {row['late_count']:<6} {row['absent_count']:<8} {row['attendance_rate']:.1f}%")
    
    print("-" * 80)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT: ATTENDANCE RECORDS")
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
        
        cursor.execute("SELECT COUNT(*) as count FROM students WHERE face_encoding IS NOT NULL")
        student_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM class_sessions WHERE status = 'completed'")
        session_count = cursor.fetchone()['count']
        
        if student_count == 0:
            print("\n❌ ERROR: No students with face encodings found!")
            print("   Please run the student faker script first.")
            return
        
        if session_count == 0:
            print("\n❌ ERROR: No completed sessions found!")
            print("   Please run faker_sessions.py first.")
            return
        
        print(f"\n✓ Found {student_count} students with face encodings")
        print(f"✓ Found {session_count} completed sessions")
        
        # Clear existing attendance
        if not clear_existing_attendance(conn):
            return
        
        # Generate attendance
        attendance = generate_attendance(conn)
        
        if not attendance:
            print("\n⚠️  No attendance records were generated")
            return
        
        # Print statistics
        print_attendance_statistics(conn)
        
        # Print samples
        print_sample_attendance(conn)
        print_student_summary(conn)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ ATTENDANCE GENERATION COMPLETE!")
        print("=" * 70)
        print(f"📊 Total Attendance Records: {len(attendance)}")
        print(f"✅ Only completed past sessions have attendance")
        print(f"✅ No sessions have 100% attendance")
        print(f"✅ No future sessions have attendance")
        print(f"✅ No cancelled/dismissed sessions have attendance")
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