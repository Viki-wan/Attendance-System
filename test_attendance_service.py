#!/usr/bin/env python3
"""
Test script for the enhanced attendance report service integration
This script tests the LecturerAttendanceReportService functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lecturer_panel.services.attendance_report_service import LecturerAttendanceReportService
import sqlite3

def test_service_initialization():
    """Test if the service can be initialized properly"""
    try:
        service = LecturerAttendanceReportService()
        print("✅ Service initialization successful")
        return service
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return None

def test_database_connection(service):
    """Test database connection and basic queries"""
    try:
        # Test basic database connection
        service.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = service.cursor.fetchall()
        print(f"✅ Database connection successful. Found {len(tables)} tables")
        
        # Check if required tables exist
        required_tables = ['students', 'instructors', 'courses', 'classes', 'class_sessions', 'attendance']
        existing_tables = [table[0] for table in tables]
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        if missing_tables:
            print(f"⚠️  Missing tables: {missing_tables}")
        else:
            print("✅ All required tables exist")
            
        return True
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

def test_service_methods(service):
    """Test the service methods"""
    try:
        # Test getting instructor courses (assuming instructor_id = 1 exists)
        courses = service.get_instructor_courses(1)
        print(f"✅ get_instructor_courses: Found {len(courses)} courses")
        
        # Test getting instructor classes
        classes = service.get_instructor_classes(1)
        print(f"✅ get_instructor_classes: Found {len(classes)} classes")
        
        # Test getting instructor students
        students = service.get_instructor_students(1)
        print(f"✅ get_instructor_students: Found {len(students)} students")
        
        # Test getting filtered attendance
        attendance = service.get_filtered_attendance(1, include_absent=True)
        print(f"✅ get_filtered_attendance: Found {len(attendance)} records")
        
        # Test getting attendance summary
        summary = service.get_attendance_summary(1)
        print(f"✅ get_attendance_summary: {summary}")
        
        return True
    except Exception as e:
        print(f"❌ Service methods test failed: {e}")
        return False

def test_report_generation(service):
    """Test report generation methods"""
    try:
        # Test student-wise report
        student_report = service.generate_student_wise_report(1, include_absent=True)
        print(f"✅ generate_student_wise_report: Generated {len(student_report)} student reports")
        
        # Test class-wise report
        class_report = service.generate_class_wise_report(1, include_absent=True)
        print(f"✅ generate_class_wise_report: Generated {len(class_report)} class reports")
        
        # Test trend data
        trend = service.get_recent_attendance_trend(1, days=7)
        print(f"✅ get_recent_attendance_trend: Found {len(trend)} trend points")
        
        return True
    except Exception as e:
        print(f"❌ Report generation test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Testing LecturerAttendanceReportService Integration")
    print("=" * 60)
    
    # Test service initialization
    service = test_service_initialization()
    if not service:
        return False
    
    # Test database connection
    if not test_database_connection(service):
        return False
    
    # Test service methods
    if not test_service_methods(service):
        return False
    
    # Test report generation
    if not test_report_generation(service):
        return False
    
    print("=" * 60)
    print("🎉 All tests passed! The integration is working correctly.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

