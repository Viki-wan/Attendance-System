"""
Master Faker Script Runner
Runs all faker scripts in the correct order
"""

import sys
import os
import subprocess
import time
from datetime import datetime

# Script order
FAKER_SCRIPTS = [
    ("1_faker_courses_instructors.py", "Courses & Instructors"),
    ("2_faker_classes_timetable.py", "Classes & Timetables"),
    ("3_faker_students.py", "Students with Face Encodings"),
    ("4_faker_sessions.py", "Class Sessions"),
    ("5_faker_attendance.py", "Attendance Records")
]

def print_header():
    """Print script header"""
    print("\n" + "=" * 70)
    print("FACE RECOGNITION ATTENDANCE SYSTEM - DATA GENERATOR")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("\nThis script will populate your database with realistic data:")
    print("  1. Courses & Instructors")
    print("  2. Classes & Timetables")
    print("  3. Students with Face Encodings")
    print("  4. Class Sessions")
    print("  5. Attendance Records")
    print("\n⚠️  WARNING: This will DELETE existing data!")
    print("=" * 70)

def confirm_execution():
    """Ask user for confirmation"""
    response = input("\n🔴 Do you want to continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("\n❌ Operation cancelled by user")
        sys.exit(0)
    
    print("\n✅ Starting data generation...\n")

def run_script(script_name, description):
    """
    Run a single faker script
    
    Args:
        script_name: Name of the script file
        description: Human-readable description
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "=" * 70)
    print(f"RUNNING: {description}")
    print("=" * 70)
    print(f"Script: {script_name}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 70)
    
    start_time = time.time()
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Print output
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        elapsed = time.time() - start_time
        
        print("-" * 70)
        print(f"✅ COMPLETED in {elapsed:.2f} seconds")
        print("=" * 70)
        
        return True
        
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print(f"❌ ERROR in {script_name}")
        print("=" * 70)
        print(f"Exit code: {e.returncode}")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        
        if e.stdout:
            print("\nSTDOUT:")
            print(e.stdout)
        
        if e.stderr:
            print("\nSTDERR:")
            print(e.stderr)
        
        print("=" * 70)
        
        return False
    
    except Exception as e:
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print(f"❌ UNEXPECTED ERROR in {script_name}")
        print("=" * 70)
        print(f"Error: {str(e)}")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print("=" * 70)
        
        return False

def print_summary(results, total_time):
    """Print execution summary"""
    print("\n\n" + "=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)
    
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    print(f"\nTotal Scripts: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total Time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
    
    print("\nScript Results:")
    print("-" * 70)
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['description']:40} ({result['time']:.2f}s)")
    
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 ALL SCRIPTS COMPLETED SUCCESSFULLY!")
        print("   Your database is now populated with realistic data.")
        print("\n📝 Next Steps:")
        print("   1. Run your Flask application")
        print("   2. Login as an instructor or admin")
        print("   3. Explore the generated data")
        print("\n🔐 Default Credentials:")
        print("   Admin:")
        print("     Username: admin")
        print("     Password: admin123")
        print("\n   Instructors:")
        print("     Username: Instructor ID (e.g., L2024001)")
        print("     Password: Same as username")
        print("\n   Students:")
        print("     Username: Student ID (e.g., S13-2024-001)")
        print("     Password: Same as username")
    else:
        print("\n⚠️  SOME SCRIPTS FAILED!")
        print("   Please check the error messages above and fix any issues.")
        print("   You may need to run individual scripts manually.")
    
    print("=" * 70)

def check_prerequisites():
    """Check if required packages are installed"""
    print("\n🔍 Checking Prerequisites...")
    
    missing = []
    
    # Check for face_recognition
    try:
        import face_recognition
        print("  ✅ face_recognition installed")
    except ImportError:
        print("  ⚠️  face_recognition not installed")
        missing.append("face_recognition")
    
    # Check for cv2
    try:
        import cv2
        print("  ✅ opencv-python installed")
    except ImportError:
        print("  ⚠️  opencv-python not installed")
        missing.append("opencv-python")
    
    # Check for faker (if you decide to use it)
    try:
        from faker import Faker
        print("  ✅ faker installed")
    except ImportError:
        print("  ℹ️  faker not installed (optional)")
    
    if missing:
        print("\n⚠️  Missing packages:")
        for pkg in missing:
            print(f"     pip install {pkg}")
        print("\n   Some features may not work without these packages.")
        print("   Continue anyway? (Scripts will generate data without face encodings)")
        
        response = input("   Continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("\n❌ Exiting...")
            sys.exit(0)

def main():
    """Main execution"""
    print_header()
    check_prerequisites()
    confirm_execution()
    
    results = []
    start_time = time.time()
    
    # Run each script
    for script_name, description in FAKER_SCRIPTS:
        script_start = time.time()
        success = run_script(script_name, description)
        script_time = time.time() - script_start
        
        results.append({
            'script': script_name,
            'description': description,
            'success': success,
            'time': script_time
        })
        
        # Stop if a script fails
        if not success:
            print(f"\n❌ Stopping execution due to failure in {script_name}")
            break
        
        # Small pause between scripts
        time.sleep(1)
    
    total_time = time.time() - start_time
    
    # Print summary
    print_summary(results, total_time)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)