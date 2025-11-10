"""
Faker Script 5: Attendance Records
Generates realistic attendance records for completed sessions
Run this AFTER faker_sessions.py
"""

import sys
import os
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.attendance import Attendance
from app.models.session import ClassSession
from app.models.student import Student
from app.models.class_model import Class

def clear_existing_data():
    """Clear existing attendance"""
    print("\n🗑️  Clearing existing attendance data...")
    
    try:
        Attendance.query.delete()
        
        db.session.commit()
        print("✅ Existing attendance data cleared")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing data: {e}")
        raise

def generate_attendance_for_session(session):
    """
    Generate attendance records for a single session
    
    Args:
        session: ClassSession object
    
    Returns:
        list: Created Attendance objects
    """
    # Get students for this class
    students = Student.query.filter_by(
        course=session.class_.course_code,
        year_of_study=session.class_.year,
        current_semester=session.class_.semester,
        is_active=True
    ).all()
    
    if not students:
        return []
    
    attendance_records = []
    
    # Determine attendance rate (70-95%)
    attendance_rate = random.uniform(0.70, 0.95)
    num_present = int(len(students) * attendance_rate)
    
    # Randomly select students who attended
    present_students = random.sample(students, num_present)
    
    # Determine who was late (5-15% of present students)
    late_rate = random.uniform(0.05, 0.15)
    num_late = int(num_present * late_rate)
    late_students = random.sample(present_students, min(num_late, len(present_students)))
    
    # Get session instructor
    instructor_id = session.created_by
    
    # Create attendance records for all students
    for student in students:
        if student in present_students:
            if student in late_students:
                status = 'Late'
            else:
                status = 'Present'
        else:
            status = 'Absent'
        
        # Calculate confidence score for face recognition (0.6-0.99)
        confidence = None
        if status in ['Present', 'Late']:
            confidence = random.uniform(0.6, 0.99)
        
        # Create attendance record
        attendance = Attendance(
            student_id=student.student_id,
            session_id=session.session_id,
            timestamp=datetime.utcnow(),  # In real system, this would be actual check-in time
            status=status,
            marked_by=instructor_id,
            method='face_recognition' if confidence else 'manual',
            confidence_score=confidence
        )
        
        attendance_records.append(attendance)
        db.session.add(attendance)
    
    # Update session attendance count
    session.attendance_count = num_present
    session.total_students = len(students)
    
    return attendance_records

def generate_all_attendance():
    """Generate attendance for all completed sessions"""
    print("\n✅ Generating Attendance Records...")
    
    # Get all completed sessions
    completed_sessions = ClassSession.query.filter_by(status='completed').all()
    
    print(f"  Found {len(completed_sessions)} completed sessions")
    
    all_attendance = []
    
    for idx, session in enumerate(completed_sessions, 1):
        if idx % 10 == 0:
            print(f"  Processing session {idx}/{len(completed_sessions)}...")
        
        attendance_records = generate_attendance_for_session(session)
        all_attendance.extend(attendance_records)
    
    db.session.commit()
    print(f"✅ {len(all_attendance)} attendance records created")
    return all_attendance

def print_statistics(attendance_records):
    """Print attendance statistics"""
    print("\n📊 Attendance Statistics:")
    print("-" * 70)
    
    total = len(attendance_records)
    present = sum(1 for a in attendance_records if a.status == 'Present')
    late = sum(1 for a in attendance_records if a.status == 'Late')
    absent = sum(1 for a in attendance_records if a.status == 'Absent')
    excused = sum(1 for a in attendance_records if a.status == 'Excused')
    
    print(f"Total Records: {total}")
    print(f"  Present: {present} ({present/total*100:.1f}%)")
    print(f"  Late: {late} ({late/total*100:.1f}%)")
    print(f"  Absent: {absent} ({absent/total*100:.1f}%)")
    print(f"  Excused: {excused} ({excused/total*100:.1f}%)")
    
    # Overall attendance rate
    attendance_rate = ((present + late) / total) * 100 if total > 0 else 0
    print(f"\nOverall Attendance Rate: {attendance_rate:.1f}%")
    
    # Face recognition vs manual
    face_rec = sum(1 for a in attendance_records if a.method == 'face_recognition')
    manual = sum(1 for a in attendance_records if a.method == 'manual')
    
    print(f"\nMarking Method:")
    print(f"  Face Recognition: {face_rec} ({face_rec/total*100:.1f}%)")
    print(f"  Manual: {manual} ({manual/total*100:.1f}%)")
    
    print("-" * 70)

def print_student_attendance_summary():
    """Print attendance summary for sample students"""
    print("\n👤 Student Attendance Summary (Sample):")
    print("-" * 70)
    
    # Get random sample of students
    students = Student.query.filter_by(is_active=True).limit(10).all()
    
    for student in students:
        total_sessions = Attendance.query.filter_by(student_id=student.student_id).count()
        
        if total_sessions == 0:
            continue
        
        present_count = Attendance.query.filter_by(
            student_id=student.student_id,
            status='Present'
        ).count()
        
        late_count = Attendance.query.filter_by(
            student_id=student.student_id,
            status='Late'
        ).count()
        
        absent_count = Attendance.query.filter_by(
            student_id=student.student_id,
            status='Absent'
        ).count()
        
        attendance_rate = ((present_count + late_count) / total_sessions) * 100
        
        print(f"{student.student_id} | {student.full_name:25} | "
              f"P:{present_count:3} L:{late_count:2} A:{absent_count:2} | "
              f"Rate: {attendance_rate:.1f}%")
    
    print("-" * 70)

def identify_low_attendance_students():
    """Identify students with low attendance (<70%)"""
    print("\n⚠️  Students with Low Attendance (<70%):")
    print("-" * 70)
    
    # Get all students with attendance records
    students = Student.query.filter_by(is_active=True).all()
    
    low_attendance_students = []
    
    for student in students:
        total_sessions = Attendance.query.filter_by(student_id=student.student_id).count()
        
        if total_sessions < 3:  # Skip students with too few sessions
            continue
        
        present_count = Attendance.query.filter_by(
            student_id=student.student_id,
            status='Present'
        ).count()
        
        late_count = Attendance.query.filter_by(
            student_id=student.student_id,
            status='Late'
        ).count()
        
        attendance_rate = ((present_count + late_count) / total_sessions) * 100
        
        if attendance_rate < 70:
            low_attendance_students.append({
                'student': student,
                'rate': attendance_rate,
                'total': total_sessions
            })
    
    # Sort by attendance rate
    low_attendance_students.sort(key=lambda x: x['rate'])
    
    if not low_attendance_students:
        print("  ✅ No students with low attendance!")
    else:
        print(f"  Found {len(low_attendance_students)} students with <70% attendance")
        print()
        
        for item in low_attendance_students[:15]:  # Show worst 15
            student = item['student']
            rate = item['rate']
            total = item['total']
            
            print(f"  {student.student_id} | {student.full_name:25} | "
                  f"{student.course} Y{student.year_of_study} | "
                  f"Rate: {rate:.1f}% ({total} sessions)")
    
    print("-" * 70)

def main():
    """Main execution"""
    print("=" * 70)
    print("FAKER SCRIPT 5: ATTENDANCE RECORDS")
    print("=" * 70)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Verify prerequisites
            session_count = ClassSession.query.count()
            completed_count = ClassSession.query.filter_by(status='completed').count()
            student_count = Student.query.count()
            
            if session_count == 0 or student_count == 0:
                print("\n❌ ERROR: Please run previous faker scripts first!")
                return
            
            print(f"\n✓ Found {session_count} sessions ({completed_count} completed)")
            print(f"✓ Found {student_count} students")
            
            # Clear existing data
            clear_existing_data()
            
            # Generate attendance
            attendance_records = generate_all_attendance()
            
            # Statistics and analysis
            print_statistics(attendance_records)
            print_student_attendance_summary()
            identify_low_attendance_students()
            
            # Summary
            print("\n" + "=" * 70)
            print("✅ DATA GENERATION COMPLETE!")
            print("=" * 70)
            print(f"✅ Attendance Records: {len(attendance_records)}")
            print(f"📊 Completed Sessions: {completed_count}")
            print(f"👥 Students Tracked: {student_count}")
            print("\n🎉 ALL FAKER SCRIPTS COMPLETED SUCCESSFULLY!")
            print("   Your database is now populated with realistic data.")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()