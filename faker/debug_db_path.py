"""
Debug script to check database configuration and paths
Run this to identify where Flask is looking for the database
"""
import sys
import os
from pathlib import Path
import sqlite3

# Get the absolute path to the project root
current_dir = os.path.dirname(os.path.abspath(__file__))  # faker folder
project_root = os.path.dirname(current_dir)  # attendance system folder
lec_panel_dir = os.path.join(project_root, 'lec_panel')

# Add to path
sys.path.insert(0, lec_panel_dir)
sys.path.insert(0, current_dir)

print("=" * 70)
print("DATABASE PATH DEBUGGING")
print("=" * 70)

print("\n📁 Directory Structure:")
print(f"Current Directory (faker): {current_dir}")
print(f"Project Root: {project_root}")
print(f"Lec Panel Directory: {lec_panel_dir}")

# Check if attendance.db exists in project root
expected_db_path = os.path.join(project_root, 'attendance.db')
print(f"\n🔍 Expected DB Path: {expected_db_path}")
print(f"   Exists: {os.path.exists(expected_db_path)}")

if os.path.exists(expected_db_path):
    # Check what tables exist in the database
    conn = sqlite3.connect(expected_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n📊 Tables in {expected_db_path}:")
    for table in tables:
        print(f"   ✓ {table}")
    
    if 'instructors' not in tables:
        print(f"\n⚠️  WARNING: 'instructors' table not found!")
        print("   You may need to run the schema creation script.")
else:
    print(f"\n❌ Database file not found at expected location!")

# Now check Flask configuration
print("\n" + "=" * 70)
print("FLASK DATABASE CONFIGURATION")
print("=" * 70)

try:
    from app import create_app
    
    app = create_app()
    
    with app.app_context():
        # Get the database URI from config
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')
        print(f"\n🔧 SQLALCHEMY_DATABASE_URI: {db_uri}")
        
        # Extract the actual path from the URI
        if db_uri.startswith('sqlite:///'):
            flask_db_path = db_uri.replace('sqlite:///', '')
            
            # Handle relative vs absolute paths
            if not os.path.isabs(flask_db_path):
                flask_db_path = os.path.join(lec_panel_dir, flask_db_path)
            
            print(f"📂 Flask DB Path (resolved): {flask_db_path}")
            print(f"   Exists: {os.path.exists(flask_db_path)}")
            
            if os.path.exists(flask_db_path):
                # Check tables in Flask's database
                conn = sqlite3.connect(flask_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                print(f"\n📊 Tables in Flask's DB:")
                for table in tables:
                    print(f"   ✓ {table}")
                
                if 'instructors' not in tables:
                    print(f"\n❌ ERROR: 'instructors' table missing in Flask's database!")
            else:
                print(f"\n❌ Flask is configured to use a database that doesn't exist!")
        
        # Compare paths
        print("\n" + "=" * 70)
        print("PATH COMPARISON")
        print("=" * 70)
        print(f"Expected DB: {expected_db_path}")
        print(f"Flask DB:    {flask_db_path if 'flask_db_path' in locals() else 'Unknown'}")
        
        if 'flask_db_path' in locals():
            if os.path.normpath(expected_db_path) == os.path.normpath(flask_db_path):
                print("\n✅ Paths match! Database configuration is correct.")
            else:
                print("\n❌ PATH MISMATCH! This is your problem!")
                print("\nSOLUTION:")
                print("1. Update your Flask config to point to the correct database, OR")
                print("2. Move/copy your database to where Flask expects it, OR")
                print("3. Create tables in the Flask database location")
        
except Exception as e:
    print(f"\n❌ Error loading Flask app: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("RECOMMENDED FIXES")
print("=" * 70)
print("""
Option 1: Update Flask Configuration
  - Edit your Flask app's config file (config.py or __init__.py)
  - Set SQLALCHEMY_DATABASE_URI to point to your actual database
  - Example: SQLALCHEMY_DATABASE_URI = 'sqlite:///C:/Users/HP/.vscode/attendance system/attendance.db'

Option 2: Copy Database to Flask Location
  - Copy your attendance.db to the location Flask expects
  - Run this script again to verify

Option 3: Initialize Database in Flask Location
  - Run your schema creation script
  - Point it to the Flask database location
  - Re-run your faker scripts
""")