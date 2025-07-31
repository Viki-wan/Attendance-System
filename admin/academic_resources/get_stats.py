import sqlite3
import datetime
from PyQt5.QtWidgets import QMessageBox
from config.utils_constants import DATABASE_PATH

class DashboardStatsManager:
    """
    A utility class to provide database-driven statistics 
    for the Academic Resource Manager dashboard.
    """
    
    @staticmethod
    def get_db_connection():
        """Create and return a database connection"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"Database Error: Could not connect to database: {e}")
            return None

    @staticmethod
    def get_course_stats():
        """Get statistics for courses"""
        conn = DashboardStatsManager.get_db_connection()
        if not conn:
            return "0 Active"
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM courses")
            count = cursor.fetchone()[0]
            return f"{count} Active"
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return "0 Active"
        finally:
            conn.close()

    @staticmethod
    def get_instructor_stats():
        """Get statistics for instructors"""
        conn = DashboardStatsManager.get_db_connection()
        if not conn:
            return "0 Instructors"
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM instructors")
            count = cursor.fetchone()[0]
            return f"{count} Instructors"
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return "0 Instructors"
        finally:
            conn.close()

    @staticmethod
    def get_sessions_stats():
        """Get statistics for class sessions in the current month"""
        conn = DashboardStatsManager.get_db_connection()
        if not conn:
            return "0 This Month"
        
        try:
            cursor = conn.cursor()
            # Get current month sessions
            cursor.execute("""
                SELECT COUNT(*) FROM class_sessions 
                WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
            """)
            count = cursor.fetchone()[0]
            return f"{count} This Month"
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return "0 This Month"
        finally:
            conn.close()

    @staticmethod
    def get_assignments_stats():
        """Get statistics for instructor course assignments"""
        conn = DashboardStatsManager.get_db_connection()
        if not conn:
            return "0 Assigned"
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM instructor_courses")
            count = cursor.fetchone()[0]
            return f"{count} Assigned"
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return "0 Assigned"
        finally:
            conn.close()

    @staticmethod
    def get_schedule_stats():
        """Get enhanced statistics for class scheduling"""
        conn = DashboardStatsManager.get_db_connection()
        if not conn:
            return "No Data"
        
        try:
            cursor = conn.cursor()
            
            # Get upcoming sessions count (next 7 days)
            cursor.execute("""
                SELECT COUNT(*) FROM class_sessions 
                WHERE date >= date('now') 
                AND date <= date('now', '+7 days')
            """)
            upcoming_week_count = cursor.fetchone()[0]
            
            # Find the next scheduled class after today
            cursor.execute("""
                SELECT cs.date, c.class_name FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                WHERE cs.date >= date('now') 
                ORDER BY cs.date ASC LIMIT 1
            """)
            next_session = cursor.fetchone()
            
            # Get unscheduled classes (classes with no sessions)
            cursor.execute("""
                SELECT COUNT(*) FROM classes c
                WHERE NOT EXISTS (
                    SELECT 1 FROM class_sessions cs
                    WHERE cs.class_id = c.class_id
                )
            """)
            unscheduled_count = cursor.fetchone()[0]
            
            # Construct the statistics message
            stats = []
            
            if upcoming_week_count > 0:
                stats.append(f"{upcoming_week_count} in 7 days")
            
            if unscheduled_count > 0:
                stats.append(f"{unscheduled_count} need scheduling")
            
            if next_session:
                next_date, next_class = next_session
                # Format date nicely (assuming YYYY-MM-DD format)
                try:
                    date_obj = datetime.datetime.strptime(next_date, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%b %d")  # e.g., "Apr 15"
                    stats.append(f"Next: {formatted_date}")
                except ValueError:
                    stats.append(f"Next: {next_date}")
            
            if not stats:
                return "None Scheduled"
            
            return " • ".join(stats)
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return "No Data"
        finally:
            conn.close()  
                      
    @staticmethod
    def get_current_date():
        """Get current date formatted for display"""
        return datetime.datetime.now().strftime("Today: %B %d, %Y")
    
    @staticmethod
    def get_student_stats():
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get total students count
            cursor.execute("SELECT COUNT(*) FROM students")
            total = cursor.fetchone()[0]
            
            # Get counts by year
            cursor.execute("""
                SELECT year_of_study, COUNT(*) 
                FROM students 
                GROUP BY year_of_study 
                ORDER BY year_of_study
            """)
            year_counts = cursor.fetchall()
            
            conn.close()
            
            # Format the stats
            stats_text = f"{total} Total Students"
            
            # Add year breakdown if there are students
            if total > 0 and year_counts:
                stats_text += " ("
                year_parts = []
                for year, count in year_counts:
                    if year:  # Check if not None
                        year_parts.append(f"Year {year}: {count}")
                    else:
                        year_parts.append("Unassigned: {count}")
                stats_text += ", ".join(year_parts)
                stats_text += ")"
                
            return stats_text
            
        except sqlite3.Error:
            return "Error loading student stats"