"""
Test Dashboard Queries Directly
This will run the exact queries the dashboard uses and show what's returned
"""

from app import create_app, db
from datetime import date, timedelta
from sqlalchemy import text

app = create_app('development')

with app.app_context():
    instructor_id = 'L2025001'
    today = date.today()
    today_str = today.isoformat()
    cutoff_date = (today - timedelta(days=30)).isoformat()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    
    print("=" * 80)
    print("TESTING DASHBOARD QUERIES")
    print("=" * 80)
    print(f"Instructor: {instructor_id}")
    print(f"Today: {today_str}")
    print(f"Cutoff (30 days ago): {cutoff_date}")
    print(f"Week start: {week_start}")
    print("=" * 80)
    
    # Test 1: Today's sessions (from get_today_sessions)
    print("\n1. TODAY'S SESSIONS QUERY")
    print("-" * 80)
    
    # Raw SQL
    raw_count = db.session.execute(
        text("SELECT COUNT(*) FROM class_sessions WHERE created_by = :instructor_id AND date = :date"),
        {'instructor_id': instructor_id, 'date': today_str}
    ).scalar()
    print(f"Raw count for today: {raw_count}")
    
    # Get actual sessions
    from app.models import ClassSession, Class
    sessions = ClassSession.query\
        .filter(
            ClassSession.created_by == instructor_id,
            ClassSession.date == today_str
        )\
        .all()
    
    print(f"ORM found: {len(sessions)} sessions")
    for session in sessions[:3]:
        print(f"  - Session {session.session_id}: class_id={session.class_id}, "
              f"date={session.date}, status={session.status}")
    
    # Test 2: Statistics query (from get_statistics_optimized)
    print("\n2. STATISTICS QUERY")
    print("-" * 80)
    
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
    
    result = db.session.execute(stats_query, {
        'instructor_id': instructor_id,
        'cutoff_date': cutoff_date,
        'today': today_str,
        'week_start': week_start
    }).fetchone()
    
    if result:
        print("Statistics Query Results:")
        print(f"  Total sessions: {result.total_sessions}")
        print(f"  Completed sessions: {result.completed_sessions}")
        print(f"  Avg attendance: {result.avg_attendance}")
        print(f"  Active classes: {result.active_classes}")
        print(f"  Total students: {result.total_students}")
        print(f"  Today total: {result.today_total}")
        print(f"  Today completed: {result.today_completed}")
        print(f"  Week total: {result.week_total}")
        print(f"  Week completed: {result.week_completed}")
    else:
        print("✗ No results from statistics query!")
    
    # Test 3: Directly call DashboardService
    print("\n3. CALLING DashboardService.get_dashboard_data()")
    print("-" * 80)
    
    from app.services.dashboard_service import DashboardService
    
    service = DashboardService()
    service.cache = None  # Disable cache
    
    try:
        dashboard_data = service.get_dashboard_data(instructor_id, date_filter=today)
        
        print("Dashboard Data Returned:")
        print(f"  Today sessions: {len(dashboard_data.get('today_sessions', []))}")
        print(f"  Upcoming sessions: {len(dashboard_data.get('upcoming_sessions', []))}")
        print(f"  Recent sessions: {len(dashboard_data.get('recent_sessions', []))}")
        
        stats = dashboard_data.get('statistics', {})
        print(f"\n  Statistics:")
        print(f"    Total sessions: {stats.get('total_sessions', 0)}")
        print(f"    Completed: {stats.get('completed_sessions', 0)}")
        print(f"    Average attendance: {stats.get('average_attendance', 0)}")
        
        quick_stats = dashboard_data.get('quick_stats', {})
        print(f"\n  Quick Stats:")
        print(f"    Today: {quick_stats.get('today', {})}")
        print(f"    This week: {quick_stats.get('this_week', {})}")
        
        # Show actual today sessions
        print(f"\n  Today's Sessions Detail:")
        for session in dashboard_data.get('today_sessions', [])[:3]:
            print(f"    - {session.get('class_name')}: {session.get('start_time')} "
                  f"(status={session.get('status')}, state={session.get('state')})")
        
    except Exception as e:
        print(f"✗ Error calling DashboardService: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Check what the web route receives
    print("\n4. SIMULATING WEB REQUEST")
    print("-" * 80)
    
    from flask import Flask
    from flask_login import LoginManager
    
    # Create a test request context
    with app.test_request_context():
        # Mock the current_user
        class MockUser:
            instructor_id = 'L2025001'
            instructor_name = 'Dr. James Kamau'
        
        from flask_login import login_user
        from app.models import Instructor
        
        real_instructor = Instructor.query.filter_by(instructor_id=instructor_id).first()
        if real_instructor:
            print(f"Instructor exists: {real_instructor.instructor_name}")
            
            # Try the actual dashboard route logic
            try:
                dashboard_service = DashboardService()
                
                dashboard_data = dashboard_service.get_dashboard_data(
                    instructor_id=instructor_id
                )
                
                print(f"\nRoute would receive:")
                print(f"  dashboard type: {type(dashboard_data)}")
                print(f"  dashboard keys: {dashboard_data.keys() if dashboard_data else 'None'}")
                
                if dashboard_data:
                    print(f"  quick_stats type: {type(dashboard_data.get('quick_stats'))}")
                    print(f"  quick_stats value: {dashboard_data.get('quick_stats')}")
                    
                    # Check if today stats exist
                    quick_stats = dashboard_data.get('quick_stats', {})
                    if 'today' in quick_stats:
                        print(f"  ✓ 'today' key exists in quick_stats")
                        print(f"    today value: {quick_stats['today']}")
                    else:
                        print(f"  ✗ 'today' key MISSING from quick_stats!")
                        print(f"    Available keys: {quick_stats.keys()}")
                
            except Exception as e:
                print(f"✗ Error in route simulation: {str(e)}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)