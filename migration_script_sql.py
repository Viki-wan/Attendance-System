#!/usr/bin/env python3
"""
SQLite Migration Script: Standardize Semester Fields
Migrate from TEXT "1.1" format to INTEGER (1 or 2)

IMPORTANT: Always backup your database before running migrations!
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path


class DatabaseMigration:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.conn = None
        self.cursor = None
        self.views = []
        
    def create_backup(self):
        """Create a backup of the database before migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.db_path.parent / f"backup_{timestamp}_{self.db_path.name}"
        
        print(f"Creating backup at: {backup_path}")
        
        # Open backup connection
        backup_conn = sqlite3.connect(backup_path)
        
        # Backup the database
        with backup_conn:
            self.conn.backup(backup_conn)
        
        backup_conn.close()
        print(f"✓ Backup created successfully: {backup_path}")
        return backup_path
    
    def connect(self):
        """Connect to the database"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        print(f"✓ Connected to database: {self.db_path}")
    
    def save_and_drop_views(self):
        """Save view definitions and drop all views before migration"""
        print("\n=== Saving and dropping views ===")
        
        # Get all views
        self.cursor.execute("""
            SELECT name, sql FROM sqlite_master 
            WHERE type='view' 
            ORDER BY name
        """)
        
        self.views = self.cursor.fetchall()
        
        if self.views:
            print(f"Found {len(self.views)} views to temporarily drop:")
            for view_name, _ in self.views:
                print(f"  - {view_name}")
                self.cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
            print("✓ All views dropped")
        else:
            print("No views found")
    
    def recreate_views(self):
        """Recreate all views after migration"""
        if not self.views:
            return
        
        print("\n=== Recreating views ===")
        for view_name, view_sql in self.views:
            try:
                self.cursor.execute(view_sql)
                print(f"✓ Recreated view: {view_name}")
            except sqlite3.Error as e:
                print(f"✗ Warning: Could not recreate view {view_name}: {e}")
                print(f"  SQL: {view_sql}")
    
    def migrate_students_table(self):
        """Migrate the students table"""
        print("\n=== Migrating STUDENTS table ===")
        
        # Create new students table
        self.cursor.execute("""
            CREATE TABLE students_new (
                student_id TEXT PRIMARY KEY,
                fname TEXT NOT NULL,
                lname TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                password TEXT,
                course TEXT,
                year_of_study INTEGER DEFAULT 1,
                current_semester INTEGER DEFAULT 1,
                image_path TEXT,
                image_hash TEXT,
                face_encoding BLOB,
                face_only_path TEXT,
                face_encoding_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Copy and transform data
        self.cursor.execute("""
            INSERT INTO students_new (
                student_id, fname, lname, email, phone, password, course,
                year_of_study, current_semester, image_path, image_hash,
                face_encoding, face_only_path, face_encoding_path,
                created_at, updated_at, is_active
            )
            SELECT 
                student_id, fname, lname, email, phone, password, course,
                year_of_study,
                CASE 
                    WHEN current_semester LIKE '%.%' THEN 
                        CAST(SUBSTR(current_semester, INSTR(current_semester, '.') + 1) AS INTEGER)
                    WHEN current_semester IN ('1', '2') THEN 
                        CAST(current_semester AS INTEGER)
                    ELSE 1
                END as current_semester,
                image_path, image_hash, face_encoding, face_only_path,
                face_encoding_path, created_at, updated_at, is_active
            FROM students
        """)
        
        rows_migrated = self.cursor.rowcount
        print(f"✓ Migrated {rows_migrated} student records")
        
        # Drop old table and rename
        self.cursor.execute("DROP TABLE students")
        self.cursor.execute("ALTER TABLE students_new RENAME TO students")
        
        # Recreate indexes
        self.cursor.execute("CREATE INDEX idx_students_id ON students(student_id)")
        self.cursor.execute("CREATE INDEX idx_students_course ON students(course)")
        self.cursor.execute("CREATE INDEX idx_students_active ON students(is_active)")
        
        # Recreate trigger
        self.cursor.execute("""
            CREATE TRIGGER update_students_timestamp 
                AFTER UPDATE ON students
                BEGIN
                    UPDATE students SET updated_at = CURRENT_TIMESTAMP 
                    WHERE student_id = NEW.student_id;
                END
        """)
        
        print("✓ Students table migrated successfully")
    
    def migrate_student_courses_table(self):
        """Migrate the student_courses table"""
        print("\n=== Migrating STUDENT_COURSES table ===")
        
        # Create new table
        self.cursor.execute("""
            CREATE TABLE student_courses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                course_code TEXT NOT NULL,
                semester INTEGER,
                year INTEGER,
                enrollment_date TEXT DEFAULT CURRENT_DATE,
                status TEXT DEFAULT 'Active',
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (course_code) REFERENCES courses(course_code),
                UNIQUE(student_id, course_code, semester, year),
                CONSTRAINT check_enrollment_status CHECK (status IN ('Active', 'Dropped', 'Completed', 'Failed')),
                CONSTRAINT check_semester CHECK (semester IN (1, 2) OR semester IS NULL)
            )
        """)
        
        # Copy and transform data
        self.cursor.execute("""
            INSERT INTO student_courses_new (
                id, student_id, course_code, semester, year,
                enrollment_date, status
            )
            SELECT 
                id, student_id, course_code,
                CASE 
                    WHEN semester LIKE '%.%' THEN 
                        CAST(SUBSTR(semester, INSTR(semester, '.') + 1) AS INTEGER)
                    WHEN semester IN ('1', '2') THEN 
                        CAST(semester AS INTEGER)
                    ELSE NULL
                END as semester,
                year, enrollment_date, status
            FROM student_courses
        """)
        
        rows_migrated = self.cursor.rowcount
        print(f"✓ Migrated {rows_migrated} student course records")
        
        # Drop old table and rename
        self.cursor.execute("DROP TABLE student_courses")
        self.cursor.execute("ALTER TABLE student_courses_new RENAME TO student_courses")
        
        # Recreate indexes
        self.cursor.execute("""
            CREATE INDEX idx_student_courses_student_semester 
            ON student_courses(student_id, semester)
        """)
        self.cursor.execute("""
            CREATE INDEX idx_student_courses_course 
            ON student_courses(course_code)
        """)
        
        print("✓ Student_courses table migrated successfully")
    
    def migrate_instructor_courses_table(self):
        """Migrate the instructor_courses table"""
        print("\n=== Migrating INSTRUCTOR_COURSES table ===")
        
        # Create new table
        self.cursor.execute("""
            CREATE TABLE instructor_courses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instructor_id TEXT NOT NULL,
                course_code TEXT NOT NULL,
                semester INTEGER,
                year INTEGER,
                is_coordinator INTEGER DEFAULT 0,
                FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
                FOREIGN KEY (course_code) REFERENCES courses(course_code),
                UNIQUE(instructor_id, course_code, semester, year),
                CONSTRAINT check_semester CHECK (semester IN (1, 2) OR semester IS NULL)
            )
        """)
        
        # Copy and transform data
        self.cursor.execute("""
            INSERT INTO instructor_courses_new (
                id, instructor_id, course_code, semester, year, is_coordinator
            )
            SELECT 
                id, instructor_id, course_code,
                CASE 
                    WHEN semester LIKE '%.%' THEN 
                        CAST(SUBSTR(semester, INSTR(semester, '.') + 1) AS INTEGER)
                    WHEN semester IN ('1', '2') THEN 
                        CAST(semester AS INTEGER)
                    ELSE NULL
                END as semester,
                year, is_coordinator
            FROM instructor_courses
        """)
        
        rows_migrated = self.cursor.rowcount
        print(f"✓ Migrated {rows_migrated} instructor course records")
        
        # Drop old table and rename
        self.cursor.execute("DROP TABLE instructor_courses")
        self.cursor.execute("ALTER TABLE instructor_courses_new RENAME TO instructor_courses")
        
        print("✓ Instructor_courses table migrated successfully")
    
    def validate_migration(self):
        """Validate the migration results"""
        print("\n=== Validating Migration ===")
        
        # Check students semester values
        self.cursor.execute("SELECT DISTINCT current_semester FROM students ORDER BY current_semester")
        student_semesters = [row[0] for row in self.cursor.fetchall()]
        print(f"Students semesters: {student_semesters}")
        
        # Validate only 1 and 2
        invalid_semesters = [s for s in student_semesters if s not in (1, 2)]
        if invalid_semesters:
            print(f"⚠ Warning: Found invalid semester values in students: {invalid_semesters}")
        
        # Check student_courses semester values
        self.cursor.execute("SELECT DISTINCT semester FROM student_courses WHERE semester IS NOT NULL ORDER BY semester")
        sc_semesters = [row[0] for row in self.cursor.fetchall()]
        print(f"Student_courses semesters: {sc_semesters}")
        
        # Check instructor_courses semester values
        self.cursor.execute("SELECT DISTINCT semester FROM instructor_courses WHERE semester IS NOT NULL ORDER BY semester")
        ic_semesters = [row[0] for row in self.cursor.fetchall()]
        print(f"Instructor_courses semesters: {ic_semesters}")
        
        # Count records by semester
        print("\nRecord counts by semester:")
        self.cursor.execute("""
            SELECT 'students' as table_name, current_semester as semester, COUNT(*) as count 
            FROM students GROUP BY current_semester
            UNION ALL
            SELECT 'student_courses', semester, COUNT(*) 
            FROM student_courses WHERE semester IS NOT NULL GROUP BY semester
            UNION ALL
            SELECT 'instructor_courses', semester, COUNT(*) 
            FROM instructor_courses WHERE semester IS NOT NULL GROUP BY semester
        """)
        
        for row in self.cursor.fetchall():
            print(f"  {row[0]}: semester {row[1]} = {row[2]} records")
        
        print("\n✓ Validation complete")
    
    def run_migration(self):
        """Run the complete migration process"""
        try:
            print("=" * 60)
            print("SQLite Migration: Standardize Semester Fields")
            print("=" * 60)
            
            # Connect to database
            self.connect()
            
            # Create backup
            backup_path = self.create_backup()
            
            # Disable foreign keys during migration
            self.cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Begin transaction
            self.conn.execute("BEGIN TRANSACTION")
            
            # Save and drop all views first
            self.save_and_drop_views()
            
            # Run migrations
            self.migrate_students_table()
            self.migrate_student_courses_table()
            self.migrate_instructor_courses_table()
            
            # Recreate views
            self.recreate_views()
            
            # Validate results
            self.validate_migration()
            
            # Commit transaction
            self.conn.commit()
            
            # Re-enable foreign keys
            self.cursor.execute("PRAGMA foreign_keys = ON")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("=" * 60)
            print(f"\nBackup saved at: {backup_path}")
            print("\nPost-migration checklist:")
            print("  □ Test application with new schema")
            print("  □ Update any code that references semester fields")
            print("  □ Archive backup after verification period")
            
        except Exception as e:
            print(f"\n✗ Error during migration: {e}")
            print("Rolling back transaction...")
            self.conn.rollback()
            print(f"Database has been rolled back. Restore from backup if needed:")
            print(f"  {backup_path}")
            raise
        
        finally:
            if self.conn:
                self.conn.close()
                print("\n✓ Database connection closed")


def main():
    # Hardcoded path
    db_path = r"C:\Users\HP\.vscode\attendance system\attendance.db"
    
    if not Path(db_path).exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    # Confirm before proceeding
    print(f"This will migrate the database: {db_path}")
    print("A backup will be created automatically.")
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Migration cancelled.")
        sys.exit(0)
    
    # Run migration
    migration = DatabaseMigration(db_path)
    migration.run_migration()


if __name__ == "__main__":
    main()