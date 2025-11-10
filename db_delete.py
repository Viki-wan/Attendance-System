"""
Database Clear Script
Safely clears all data from the attendance system database while preserving schema
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime
import shutil


class DatabaseCleaner:
    """Handles safe database cleanup operations"""
    
    def __init__(self, db_path='attendance.db'):
        self.db_path = Path(db_path)
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self):
        """Create a backup of the database before clearing"""
        if not self.db_path.exists():
            print(f"❌ Database not found: {self.db_path}")
            return False
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'attendance_backup_{timestamp}.db'
        
        try:
            shutil.copy2(self.db_path, backup_path)
            print(f"✅ Backup created: {backup_path}")
            return True
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def get_table_list(self, conn):
        """Get list of all tables in the database"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        return [row[0] for row in cursor.fetchall()]
    
    def get_table_counts(self, conn):
        """Get record counts for all tables"""
        tables = self.get_table_list(conn)
        counts = {}
        
        for table in tables:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
            
        return counts
    
    def clear_all_data(self, create_backup=True):
        """Clear all data from all tables"""
        
        if not self.db_path.exists():
            print(f"❌ Database not found: {self.db_path}")
            return False
        
        # Create backup first
        if create_backup:
            if not self.create_backup():
                response = input("Backup failed. Continue anyway? (yes/no): ")
                if response.lower() != 'yes':
                    print("Operation cancelled.")
                    return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Show current data counts
            print("\n📊 Current data counts:")
            counts = self.get_table_counts(conn)
            total_records = sum(counts.values())
            
            for table, count in sorted(counts.items()):
                if count > 0:
                    print(f"   {table}: {count:,} records")
            
            print(f"\n   Total records: {total_records:,}")
            
            if total_records == 0:
                print("\n✅ Database is already empty!")
                conn.close()
                return True
            
            # Confirm deletion
            print(f"\n⚠️  WARNING: This will delete all {total_records:,} records!")
            response = input("Type 'DELETE ALL' to confirm: ")
            
            if response != 'DELETE ALL':
                print("Operation cancelled.")
                conn.close()
                return False
            
            # Disable foreign key constraints temporarily
            conn.execute("PRAGMA foreign_keys = OFF")
            
            # Get list of tables to clear
            tables = self.get_table_list(conn)
            
            print("\n🗑️  Clearing tables...")
            
            # Clear each table
            for table in tables:
                try:
                    conn.execute(f"DELETE FROM {table}")
                    # Reset autoincrement counters
                    conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                    print(f"   ✓ Cleared: {table}")
                except Exception as e:
                    print(f"   ✗ Error clearing {table}: {e}")
            
            # Re-enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Commit changes
            conn.commit()
            
            # Verify all tables are empty
            print("\n✅ Verification:")
            final_counts = self.get_table_counts(conn)
            all_empty = all(count == 0 for count in final_counts.values())
            
            if all_empty:
                print("   All tables cleared successfully!")
            else:
                print("   Some tables still have data:")
                for table, count in final_counts.items():
                    if count > 0:
                        print(f"   {table}: {count} records")
            
            # Vacuum to reclaim space
            print("\n🔧 Optimizing database...")
            conn.execute("VACUUM")
            print("   Database optimized!")
            
            conn.close()
            
            # Show final database size
            size_mb = self.db_path.stat().st_size / (1024 * 1024)
            print(f"\n📦 Final database size: {size_mb:.2f} MB")
            
            return all_empty
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False
    
    def clear_specific_tables(self, tables, create_backup=True):
        """Clear data from specific tables only"""
        
        if not self.db_path.exists():
            print(f"❌ Database not found: {self.db_path}")
            return False
        
        if create_backup:
            if not self.create_backup():
                response = input("Backup failed. Continue anyway? (yes/no): ")
                if response.lower() != 'yes':
                    print("Operation cancelled.")
                    return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Validate tables exist
            all_tables = self.get_table_list(conn)
            invalid_tables = [t for t in tables if t not in all_tables]
            
            if invalid_tables:
                print(f"❌ Invalid tables: {', '.join(invalid_tables)}")
                conn.close()
                return False
            
            # Show current counts
            print("\n📊 Current data in selected tables:")
            for table in tables:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   {table}: {count:,} records")
            
            # Confirm
            response = input(f"\nClear these {len(tables)} tables? (yes/no): ")
            if response.lower() != 'yes':
                print("Operation cancelled.")
                conn.close()
                return False
            
            # Clear tables
            conn.execute("PRAGMA foreign_keys = OFF")
            
            print("\n🗑️  Clearing tables...")
            for table in tables:
                try:
                    conn.execute(f"DELETE FROM {table}")
                    conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                    print(f"   ✓ Cleared: {table}")
                except Exception as e:
                    print(f"   ✗ Error clearing {table}: {e}")
            
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
            conn.close()
            
            print("\n✅ Selected tables cleared successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False
    
    def clear_uploads_folder(self):
        """Clear all uploaded files (photos, face encodings, reports)"""
        uploads_dir = Path('uploads')
        
        if not uploads_dir.exists():
            print("No uploads folder found.")
            return
        
        folders_to_clear = [
            'face_encodings',
            'face_only',
            'student_photos',
            'reports'
        ]
        
        print("\n🗑️  Clearing uploads...")
        total_deleted = 0
        
        for folder_name in folders_to_clear:
            folder_path = uploads_dir / folder_name
            if folder_path.exists():
                files = list(folder_path.glob('*'))
                count = len(files)
                
                for file in files:
                    if file.is_file():
                        file.unlink()
                
                total_deleted += count
                print(f"   ✓ Cleared {count} files from {folder_name}/")
        
        print(f"\n✅ Total files deleted: {total_deleted}")


def main():
    """Main execution"""
    
    print("=" * 60)
    print("   DATABASE CLEANER - Attendance System")
    print("=" * 60)
    
    # Check if database exists
    db_path = Path('attendance.db')
    if not db_path.exists():
        print("\n❌ Database not found: attendance.db")
        print("   Make sure you're in the correct directory.")
        return
    
    cleaner = DatabaseCleaner(db_path)
    
    print("\nOptions:")
    print("1. Clear ALL data from database")
    print("2. Clear specific tables")
    print("3. Clear uploads folder only")
    print("4. Clear everything (database + uploads)")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == '1':
        # Clear all data
        cleaner.clear_all_data(create_backup=True)
        
    elif choice == '2':
        # Clear specific tables
        conn = sqlite3.connect(db_path)
        all_tables = cleaner.get_table_list(conn)
        conn.close()
        
        print("\nAvailable tables:")
        for i, table in enumerate(all_tables, 1):
            print(f"{i:2d}. {table}")
        
        print("\nEnter table numbers separated by commas (e.g., 1,3,5)")
        print("Or table names separated by commas (e.g., attendance,students)")
        selection = input("Selection: ").strip()
        
        if selection:
            # Parse selection
            selected_tables = []
            for item in selection.split(','):
                item = item.strip()
                if item.isdigit():
                    idx = int(item) - 1
                    if 0 <= idx < len(all_tables):
                        selected_tables.append(all_tables[idx])
                else:
                    if item in all_tables:
                        selected_tables.append(item)
            
            if selected_tables:
                cleaner.clear_specific_tables(selected_tables, create_backup=True)
            else:
                print("❌ No valid tables selected.")
        
    elif choice == '3':
        # Clear uploads only
        response = input("Clear all uploaded files? (yes/no): ")
        if response.lower() == 'yes':
            cleaner.clear_uploads_folder()
        
    elif choice == '4':
        # Clear everything
        print("\n⚠️  This will clear ALL database data AND all uploaded files!")
        response = input("Type 'DELETE EVERYTHING' to confirm: ")
        
        if response == 'DELETE EVERYTHING':
            cleaner.clear_all_data(create_backup=True)
            cleaner.clear_uploads_folder()
            print("\n✅ Everything cleared!")
        else:
            print("Operation cancelled.")
    
    elif choice == '5':
        print("Goodbye!")
        return
    
    else:
        print("❌ Invalid choice!")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)