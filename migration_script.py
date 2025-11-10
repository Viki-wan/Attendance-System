"""
Database Migration Script
Fixes data type inconsistencies and adds performance indexes
Run this to update your existing database
"""

import sqlite3
import os
from datetime import datetime
import shutil

def backup_database(db_path):
    """Create a backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")
    return backup_path

def check_column_type(cursor, table, column):
    """Check the current type of a column"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    for col in columns:
        if col[1] == column:
            return col[2]  # Return type
    return None

def migrate_database(db_path):
    """Main migration function"""
    
    print("=" * 60)
    print("DATABASE MIGRATION SCRIPT")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"✗ Database not found: {db_path}")
        return False
    
    # Backup database
    print("\n1. Creating backup...")
    backup_path = backup_database(db_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("\n2. Checking schema...")
        
        # Check problematic columns
        issues = []
        
        tables_to_check = {
            'class_sessions': [('created_by', 'TEXT')],
            'attendance': [('marked_by', 'TEXT')],
            'class_instructors': [('instructor_id', 'TEXT')],
            'instructor_courses': [('instructor_id', 'TEXT')],
            'lecturer_preferences': [('instructor_id', 'TEXT')],
            'session_dismissals': [('instructor_id', 'TEXT')],
            'system_metrics': [('instructor_id', 'TEXT')]
        }
        
        for table, columns in tables_to_check.items():
            for column, expected_type in columns:
                current_type = check_column_type(cursor, table, column)
                if current_type and current_type != expected_type:
                    issues.append((table, column, current_type, expected_type))
                    print(f"  ⚠ {table}.{column}: {current_type} → needs {expected_type}")
        
        if not issues:
            print("  ✓ All column types are correct")
        else:
            print(f"\n  Found {len(issues)} issues to fix")
        
        # SQLite doesn't support ALTER COLUMN, so we need to recreate tables
        if issues:
            print("\n3. Fixing column types...")
            
            for table, column, old_type, new_type in issues:
                print(f"  Fixing {table}.{column}...")
                
                # Get table schema
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                create_sql = cursor.fetchone()[0]
                
                # Create temporary table
                temp_table = f"{table}_temp"
                temp_sql = create_sql.replace(f"CREATE TABLE {table}", f"CREATE TABLE {temp_table}")
                temp_sql = temp_sql.replace(f"{column} {old_type}", f"{column} {new_type}")
                
                cursor.execute(temp_sql)
                
                # Copy data
                cursor.execute(f"SELECT * FROM {table}")
                columns_list = [description[0] for description in cursor.description]
                data = cursor.fetchall()
                
                if data:
                    placeholders = ','.join(['?' for _ in columns_list])
                    cursor.executemany(
                        f"INSERT INTO {temp_table} ({','.join(columns_list)}) VALUES ({placeholders})",
                        data
                    )
                
                # Drop old table and rename
                cursor.execute(f"DROP TABLE {table}")
                cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {table}")
                
                print(f"    ✓ {table}.{column} fixed")
        
        print("\n4. Adding performance indexes...")
        
        # List of indexes to create
        indexes = [
            ("idx_class_sessions_instructor_date", 
             "CREATE INDEX IF NOT EXISTS idx_class_sessions_instructor_date ON class_sessions(created_by, date, status)"),
            ("idx_class_sessions_date", 
             "CREATE INDEX IF NOT EXISTS idx_class_sessions_date ON class_sessions(date)"),
            ("idx_class_sessions_status", 
             "CREATE INDEX IF NOT EXISTS idx_class_sessions_status ON class_sessions(status)"),
            ("idx_class_sessions_class_date", 
             "CREATE INDEX IF NOT EXISTS idx_class_sessions_class_date ON class_sessions(class_id, date, status)"),
            ("idx_class_sessions_created_by", 
             "CREATE INDEX IF NOT EXISTS idx_class_sessions_created_by ON class_sessions(created_by)"),
            ("idx_attendance_student_session", 
             "CREATE INDEX IF NOT EXISTS idx_attendance_student_session ON attendance(student_id, session_id, status)"),
            ("idx_attendance_status", 
             "CREATE INDEX IF NOT EXISTS idx_attendance_status ON attendance(status)"),
            ("idx_attendance_session", 
             "CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance(session_id)"),
            ("idx_attendance_student_status", 
             "CREATE INDEX IF NOT EXISTS idx_attendance_student_status ON attendance(student_id, status)"),
            ("idx_notifications_user", 
             "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, user_type, created_at)"),
            ("idx_notifications_unread", 
             "CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, user_type, is_read)"),
            ("idx_students_id", 
             "CREATE INDEX IF NOT EXISTS idx_students_id ON students(student_id)"),
            ("idx_students_course", 
             "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)"),
            ("idx_classes_id_active", 
             "CREATE INDEX IF NOT EXISTS idx_classes_id_active ON classes(class_id, is_active)"),
            ("idx_activity_log_user_type", 
             "CREATE INDEX IF NOT EXISTS idx_activity_log_user_type ON activity_log(user_id, user_type)")
        ]
        
        created_count = 0
        for idx_name, idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
                print(f"  ✓ {idx_name}")
                created_count += 1
            except sqlite3.Error as e:
                print(f"  ⚠ {idx_name}: {e}")
        
        print(f"\n  Created {created_count}/{len(indexes)} indexes")
        
        # Add activity log columns if missing
        print("\n5. Updating activity_log table...")
        try:
            cursor.execute("ALTER TABLE activity_log ADD COLUMN ip_address TEXT")
            print("  ✓ Added ip_address column")
        except sqlite3.OperationalError:
            print("  ✓ ip_address column already exists")
        
        try:
            cursor.execute("ALTER TABLE activity_log ADD COLUMN user_agent TEXT")
            print("  ✓ Added user_agent column")
        except sqlite3.OperationalError:
            print("  ✓ user_agent column already exists")
        
        try:
            cursor.execute("ALTER TABLE activity_log ADD COLUMN session_id TEXT")
            print("  ✓ Added session_id column")
        except sqlite3.OperationalError:
            print("  ✓ session_id column already exists")
        
        # Add cache-related settings
        print("\n6. Adding cache settings...")
        cache_settings = [
            ("cache_default_timeout", "300", "Default cache timeout in seconds", "performance"),
            ("enable_redis_cache", "1", "Enable Redis caching", "performance")
        ]
        
        for key, value, desc, category in cache_settings:
            try:
                cursor.execute(
                    "INSERT INTO settings (setting_key, setting_value, description, category) VALUES (?, ?, ?, ?)",
                    (key, value, desc, category)
                )
                print(f"  ✓ Added setting: {key}")
            except sqlite3.IntegrityError:
                print(f"  ✓ Setting already exists: {key}")
        
        # Commit changes
        conn.commit()
        
        print("\n7. Verifying migration...")
        
        # Check index count
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
        index_count = cursor.fetchone()[0]
        print(f"  ✓ Total indexes: {index_count}")
        
        # Check some critical indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
            ORDER BY name
        """)
        custom_indexes = cursor.fetchall()
        print(f"  ✓ Custom indexes: {len(custom_indexes)}")
        
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\nBackup saved at: {backup_path}")
        print("\nNext steps:")
        print("1. Test your application")
        print("2. Run: flask cache-stats")
        print("3. Monitor performance improvements")
        print("4. If everything works, you can delete the backup")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print(f"Database has been rolled back")
        print(f"Backup is available at: {backup_path}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verify_migration(db_path):
    """Verify the migration was successful"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)
    
    # Check column types
    print("\n1. Column Types:")
    tables = ['class_sessions', 'attendance', 'class_instructors']
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        print(f"\n  {table}:")
        for col in columns:
            if 'instructor' in col[1] or col[1] in ['created_by', 'marked_by']:
                print(f"    {col[1]}: {col[2]}")
    
    # Check indexes
    print("\n2. Indexes:")
    cursor.execute("""
        SELECT name, tbl_name FROM sqlite_master 
        WHERE type='index' AND name LIKE 'idx_%'
        ORDER BY tbl_name, name
    """)
    indexes = cursor.fetchall()
    
    current_table = None
    for idx_name, tbl_name in indexes:
        if current_table != tbl_name:
            print(f"\n  {tbl_name}:")
            current_table = tbl_name
        print(f"    ✓ {idx_name}")
    
    # Check settings
    print("\n3. Cache Settings:")
    cursor.execute("""
        SELECT setting_key, setting_value 
        FROM settings 
        WHERE category='performance'
    """)
    settings = cursor.fetchall()
    for key, value in settings:
        print(f"  {key}: {value}")
    
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    """Run migration"""
    import sys
    
    # Get database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "attendance.db"
    
    print(f"Database: {db_path}\n")
    
    # Confirm
    response = input("This will modify your database. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled")
        sys.exit(0)
    
    # Run migration
    success = migrate_database(db_path)
    
    if success:
        # Verify
        verify_migration(db_path)
    else:
        print("\nMigration failed. Please check the error messages above.")
        sys.exit(1)