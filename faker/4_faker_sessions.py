"""
Faker Script 4: Class Sessions
Generates realistic class sessions based on timetables
Run this AFTER faker_students.py
"""

import sys
import os
from datetime import datetime, date, timedelta
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import ClassSession
from app.models.class_model import Class
from app.models.timetable import Timetable
from app.models.student import Student
from faker_config import (
    CURRENT_SEMESTER, SEMESTER_DATES, is_holiday, is_weekend,
    get_weekdays_in_range
)

def clear_existing_data():
    """Clear existing sessions"""
    print("\n🗑️  Clearing existing session data...")
    
    try:
        # Don't delete attendance yet - will be done in next script
        ClassSession.query.delete()
        
        db.session.commit()
        print("✅ Existing session data cleared")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing data: {e}")
        raise

def get_date_range():
    """Get date range for session generation"""
    # Generate sessions for current semester
    semester_info = SEMESTER_DATES.get(CURRENT_SEMESTER)
    
    if not semester_info:
        print(f"⚠️  No date range found for semester {CURRENT_SEMESTER}")
        # Fallback: generate for next 30 days
        start_date = date.today()
        end_date = start_date + timedelta(days=30)
    else:
        start_date = datetime.strptime(semester_info["start"], "%Y-%m-%d").date()
        end_date = datetime.strptime(semester_info["end"], "%Y-%m-%d").date()
    
    return start_date, end_date

def generate_sessions_from_timetable():
    """Generate class sessions based on timetable entries"""
    print("\n📅 Generating Class Sessions from Timetables...")
    
    start_date, end_date = get_date_range()
    
    print(f"  Date Range: {start_date} to {end_date}")
    
    # Get all active timetables
    timetables = Timetable.query.filter_by(is_active=True).all()
    
    if not timetables:
        print("  ⚠️  No timetables found!")
        return []
    
    print(f"  Found {len(timetables)} active timetable entries")
    
    sessions = []
    current_date = start_date
    
    # Generate sessions for each day in range
    while current_date <= end_date:
        # Skip weekends and holidays
        if is_weekend(current_date) or is_holiday(current_date):
            current_date += timedelta(days=1)
            continue
        
        # Get day of week (0=Sunday, 1=Monday, ...)
        # Python's weekday() returns 0=Monday, so we need to adjust
        day_of_week = (current_date.weekday() + 1) % 7
        
        # Find timetables for this day
        day_timetables = [tt for tt in timetables if tt.day_of_week == day_of_week]
        
        for timetable in day_timetables:
            # Check if session already exists
            existing = ClassSession.query.filter_by(
                class_id=timetable.class_id,
                date=current_date.strftime('%Y-%m-%d'),
                start_time=timetable.start_time
            ).first()
            
            if existing:
                continue
            
            # Get class info
            class_obj = Class.query.get(timetable.class_id)
            if not class_obj:
                continue
            
            # Get instructor (first assigned instructor)
            instructor = class_obj.instructors[0] if class_obj.instructors else None
            
            if not instructor:
                print(f"    ⚠️  No instructor for {class_obj.class_name}")
                continue
            
            # Get student count for this class
            student_count = Student.query.filter_by(
                course=class_obj.course_code,
                year_of_study=class_obj.year,
                current_semester=class_obj.semester,
                is_active=True
            ).count()
            
            # Determine session status based on date
            today = date.today()
            
            if current_date < today:
                status = 'completed'
            elif current_date == today:
                # Check if time has passed
                now = datetime.now().time()
                session_end = datetime.strptime(timetable.end_time, '%H:%M').time()
                
                if now > session_end:
                    status = 'completed'
                else:
                    session_start = datetime.strptime(timetable.start_time, '%H:%M').time()
                    if now >= session_start:
                        status = 'ongoing'
                    else:
                        status = 'scheduled'
            else:
                status = 'scheduled'
            
            # For completed sessions, simulate attendance (70-95% attendance rate)
            attendance_count = 0
            if status == 'completed':
                attendance_rate = random.uniform(0.70, 0.95)
                attendance_count = int(student_count * attendance_rate)
            
            # Create session
            session = ClassSession(
                class_id=timetable.class_id,
                date=current_date.strftime('%Y-%m-%d'),
                start_time=timetable.start_time,
                end_time=timetable.end_time,
                status=status,
                created_by=instructor.instructor_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                attendance_count=attendance_count,
                total_students=student_count
            )
            
            sessions.append(session)
            db.session.add(session)
        
        current_date += timedelta(days=1)
    
    db.session.commit()
    print(f"✅ {len(sessions)} sessions created")
    return sessions

def print_statistics(sessions):
    """Print session statistics"""
    print("\n📊 Session Statistics:")
    print("-" * 70)
    
    total = len(sessions)
    completed = sum(1 for s in sessions if s.status == 'completed')
    ongoing = sum(1 for s in sessions if s.status == 'ongoing')
    scheduled = sum(1 for s in sessions if s.status == 'scheduled')
    
    print(f"Total Sessions: {total}")
    print(f"  Completed: {completed}")
    print(f"  Ongoing: {ongoing}")
    print(f"  Scheduled: {scheduled}")
    
    # By status percentage
    if total > 0:
        print(f"\nCompletion Rate: {completed/total*100:.1f}%")
    
    # Average attendance for completed sessions
    if completed > 0:
        avg_attendance = sum(s.attendance_count for s in sessions if s.status == 'completed') / completed
        avg_total = sum(s.total_students for s in sessions if s.status == 'completed') / completed
        if avg_total > 0:
            avg_rate = (avg_attendance / avg_total) * 100
            print(f"Average Attendance Rate: {avg_rate:.1f}%")
    
    print("-" * 70)

def print_sample_sessions(sessions):
    """Print sample sessions"""
    print("\n📋 Sample Sessions (Recent 15):")
    print("-" * 70)
    
    # Sort by date descending
    sorted_sessions = sorted(sessions, key=lambda s: s.date, reverse=True)
    
    for session in sorted_sessions[:15]:
        class_name = session.class_.class_name if session.class_ else "Unknown"
        attendance_info = f"{session.attendance_count}/{session.total_students}"
        
        status_emoji = {
            'completed': '✅',
            'ongoing': '🟢',
            'scheduled': '📅',
            'cancelled': '❌'
        }.get(session.status, '❓')
        
        print(f"{status_emoji} {session.date} {session.start_time} | {class_name[:40]:40} | {attendance_info:8} | {session.status}")
    
    print(f"... and {len(sessions) - 15} more")
    print("-" * 70)

def print_upcoming_sessions():
    """Print upcoming sessions for today and tomorrow"""
    print("\n📅 Upcoming Sessions (Today & Tomorrow):")
    print("-" * 70)
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    upcoming = ClassSession.query.filter(
        ClassSession.date.in_([today.strftime('%Y-%m-%d'), tomorrow.strftime('%Y-%m-%d')]),
        ClassSession.status.in_(['scheduled', 'ongoing'])
    ).order_by(ClassSession.date, ClassSession.start_time).all()
    
    if not upcoming:
        print("  No upcoming sessions")
    else:
        for session in upcoming:
            day_label = "Today" if session.date == today.strftime('%Y-%m-%d') else "Tomorrow"
            class_name = session.class_.class_name if session.class_ else "Unknown"
            instructor_name = session.instructor.instructor_name if session.instructor else "Unknown"
            
            print(f"{day_label:8} | {session.start_time}-{session.end_time} | {class_name[:35]:35} | {instructor_name}")
    
    print("-" * 70)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT 4: CLASS SESSIONS")
    print("=" * 70)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Verify prerequisites
            timetable_count = Timetable.query.count()
            class_count = Class.query.count()
            student_count = Student.query.count()
            
            if timetable_count == 0 or class_count == 0:
                print("\n❌ ERROR: Please run previous faker scripts first!")
                return
            
            print(f"\n✓ Found {timetable_count} timetable entries")
            print(f"✓ Found {class_count} classes")
            print(f"✓ Found {student_count} students")
            
            # Clear existing data
            clear_existing_data()
            
            # Generate sessions
            sessions = generate_sessions_from_timetable()
            
            # Statistics and samples
            print_statistics(sessions)
            print_sample_sessions(sessions)
            print_upcoming_sessions()
            
            # Summary
            print("\n" + "=" * 70)
            print("✅ DATA GENERATION COMPLETE!")
            print("=" * 70)
            print(f"📅 Sessions: {len(sessions)}")
            print(f"✅ Completed: {sum(1 for s in sessions if s.status == 'completed')}")
            print(f"🟢 Ongoing: {sum(1 for s in sessions if s.status == 'ongoing')}")
            print(f"📅 Scheduled: {sum(1 for s in sessions if s.status == 'scheduled')}")
            print("\n💡 Next: Run faker_attendance.py to generate attendance records")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()