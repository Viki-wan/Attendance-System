"""
Database Diagnostic Script
Run this to check what data exists for instructor L2025001
"""

from app import create_app, db
from app.models import ClassSession, Class, Student, Attendance, Instructor
from datetime import date, timedelta
from sqlalchemy import text

app = create_app('development')

with app.app_context():
    instructor_id = 'L2025001'
    
    print("=" * 80)
    print("DATABASE DIAGNOSTIC FOR INSTRUCTOR:", instructor_id)
    print("=" * 80)
    
    # 1. Check if instructor exists
    print("\n1. CHECKING INSTRUCTOR...")
    instructor = Instructor.query.filter_by(instructor_id=instructor_id).first()
    if instructor:
        print(f"   ✓ Instructor found: {instructor.instructor_name}")
    else:
        print(f"   ✗ Instructor NOT found with ID: {instructor_id}")
        print("\nAvailable instructors:")
        for inst in Instructor.query.all():
            print(f"   - {inst.instructor_id}: {inst.instructor_name}")
        exit()
    
    # 2. Check class_sessions table
    print("\n2. CHECKING CLASS SESSIONS...")
    print(f"   Looking for sessions with created_by = '{instructor_id}'")
    
    # Check data type of created_by column
    result = db.session.execute(text("PRAGMA table_info(class_sessions)")).fetchall()
    for col in result:
        if col[1] == 'created_by':
            print(f"   Column 'created_by' type: {col[2]}")
    
    # Raw SQL query
    raw_sessions = db.session.execute(
        text("SELECT session_id, class_id, date, status, created_by FROM class_sessions WHERE created_by = :instructor_id LIMIT 5"),
        {'instructor_id': instructor_id}
    ).fetchall()
    
    print(f"   Total sessions (raw SQL): {len(raw_sessions)}")
    if raw_sessions:
        print("   Sample sessions:")
        for session in raw_sessions:
            print(f"     - Session {session[0]}: {session[1]} on {session[2]} (status: {session[3]}, created_by: {session[4]})")
    
    # ORM query
    orm_sessions = ClassSession.query.filter_by(created_by=instructor_id).all()
    print(f"   Total sessions (ORM): {len(orm_sessions)}")
    
    # Check if there's a type mismatch
    print("\n3. CHECKING FOR TYPE MISMATCHES...")
    all_creators = db.session.execute(
        text("SELECT DISTINCT created_by, typeof(created_by) FROM class_sessions")
    ).fetchall()
    print(f"   Distinct created_by values and their types:")
    for creator, type_name in all_creators:
        print(f"     - '{creator}' (type: {type_name})")
    
    # 4. Check today's date
    print("\n4. CHECKING DATE FORMAT...")
    today = date.today()
    print(f"   Today's date (Python): {today}")
    print(f"   Today's date (ISO): {today.isoformat()}")
    
    today_sessions = db.session.execute(
        text("SELECT COUNT(*) FROM class_sessions WHERE date = :today AND created_by = :instructor_id"),
        {'today': today.isoformat(), 'instructor_id': instructor_id}
    ).scalar()
    print(f"   Sessions today: {today_sessions}")
    
    # Check date formats in database
    sample_dates = db.session.execute(
        text("SELECT DISTINCT date FROM class_sessions LIMIT 5")
    ).fetchall()
    print(f"   Sample dates in database:")
    for date_val in sample_dates:
        print(f"     - {date_val[0]}")
    
    # 5. Check last 30 days
    print("\n5. CHECKING LAST 30 DAYS...")
    cutoff = (today - timedelta(days=30)).isoformat()
    print(f"   Cutoff date: {cutoff}")
    
    recent_sessions = db.session.execute(
        text("SELECT COUNT(*) FROM class_sessions WHERE created_by = :instructor_id AND date >= :cutoff"),
        {'instructor_id': instructor_id, 'cutoff': cutoff}
    ).scalar()
    print(f"   Sessions in last 30 days: {recent_sessions}")
    
    # 6. Check attendance records
    print("\n6. CHECKING ATTENDANCE RECORDS...")
    attendance_count = db.session.execute(
        text("""
            SELECT COUNT(*) 
            FROM attendance a 
            JOIN class_sessions cs ON cs.session_id = a.session_id 
            WHERE cs.created_by = :instructor_id
        """),
        {'instructor_id': instructor_id}
    ).scalar()
    print(f"   Total attendance records: {attendance_count}")
    
    # 7. Check classes
    print("\n7. CHECKING CLASSES...")
    classes = db.session.execute(
        text("""
            SELECT DISTINCT c.class_id, c.class_name 
            FROM classes c 
            JOIN class_sessions cs ON cs.class_id = c.class_id 
            WHERE cs.created_by = :instructor_id
        """),
        {'instructor_id': instructor_id}
    ).fetchall()
    print(f"   Classes taught by instructor: {len(classes)}")
    for class_info in classes:
        print(f"     - {class_info[0]}: {class_info[1]}")
    
    # 8. Run the exact query from dashboard_service
    print("\n8. RUNNING DASHBOARD SERVICE QUERY...")
    try:
        stats_query = text("""
            WITH session_stats AS (
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                    AVG(CASE 
                        WHEN status = 'completed' AND total_students > 0 
                        THEN (attendance_count * 100.0 / total_students) 
                        ELSE NULL 
                    END) as avg_attendance,
                    COUNT(DISTINCT class_id) as active_classes,
                    SUM(CASE WHEN date = :today THEN 1 ELSE 0 END) as today_total,
                    SUM(CASE WHEN date = :today AND status = 'completed' THEN 1 ELSE 0 END) as today_completed,
                    SUM(CASE WHEN date >= :week_start AND date <= :today THEN 1 ELSE 0 END) as week_total,
                    SUM(CASE WHEN date >= :week_start AND date <= :today AND status = 'completed' THEN 1 ELSE 0 END) as week_completed
                FROM class_sessions
                WHERE created_by = :instructor_id AND date >= :cutoff_date
            ),
            student_stats AS (
                SELECT COUNT(DISTINCT a.student_id) as total_students
                FROM attendance a
                JOIN class_sessions cs ON cs.session_id = a.session_id
                WHERE cs.created_by = :instructor_id AND cs.date >= :cutoff_date
            )
            SELECT 
                ss.total_sessions,
                ss.completed_sessions,
                COALESCE(ss.avg_attendance, 0) as avg_attendance,
                ss.active_classes,
                st.total_students,
                ss.today_total,
                ss.today_completed,
                ss.week_total,
                ss.week_completed
            FROM session_stats ss, student_stats st
        """)
        
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        
        result = db.session.execute(stats_query, {
            'instructor_id': instructor_id,
            'cutoff_date': cutoff,
            'today': today.isoformat(),
            'week_start': week_start
        }).fetchone()
        
        if result:
            print("   Query results:")
            print(f"     Total sessions: {result.total_sessions}")
            print(f"     Completed sessions: {result.completed_sessions}")
            print(f"     Avg attendance: {result.avg_attendance}")
            print(f"     Active classes: {result.active_classes}")
            print(f"     Total students: {result.total_students}")
            print(f"     Today total: {result.today_total}")
            print(f"     Today completed: {result.today_completed}")
            print(f"     Week total: {result.week_total}")
            print(f"     Week completed: {result.week_completed}")
        else:
            print("   ✗ Query returned no results!")
    
    except Exception as e:
        print(f"   ✗ Error running query: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)