# attendance_statistics.py
from datetime import datetime, timedelta
from admin.db_service import DatabaseService

class AttendanceStatistics:
    """Calculate and provide attendance statistics"""
    
    def __init__(self, db_service):
        """Initialize with database service"""
        self.db_service = db_service or DatabaseService
    
    def calculate_statistics(self, filters):
        """Calculate attendance statistics based on provided filters
        
        Args:
            filters (dict): Filter criteria including date range, course, class, etc.
            
        Returns:
            dict: Dictionary containing calculated statistics
        """
        # Extract filter parameters from the filters dictionary
        start_date = filters.get('start_date', None)
        end_date = filters.get('end_date', None)
        course_code = filters.get('course_code', None)
        instructor_id = filters.get('instructor_id', None)
        class_id = filters.get('class_id', None)
        year_of_study = filters.get('year_of_study', None)
        semester = filters.get('semester', None)
        
        # Get attendance records using existing method in DatabaseService
        attendance_records = self.db_service.get_attendance_report(
            start_date=start_date,
            end_date=end_date,
            course_code=course_code,
            instructor_id=instructor_id,
            class_id=class_id,
            year_of_study=year_of_study,
            semester=semester
        )
        
        # Calculate statistics
        total_sessions = self._count_unique_sessions(attendance_records)
        total_students = self._count_unique_students(attendance_records)
        attendance_data = self._calculate_daily_attendance(attendance_records)
        attendance_rate = self._calculate_attendance_rate(attendance_records)
        
        # Additional statistics
        present_count = sum(1 for record in attendance_records if record['status'] == 'Present')
        absent_count = len(attendance_records) - present_count
        
        # Group attendance by course and class
        course_stats = self._calculate_course_stats(attendance_records)
        class_stats = self._calculate_class_stats(attendance_records)
        
        return {
            'total_sessions': total_sessions,
            'total_students': total_students,
            'attendance_data': attendance_data,
            'attendance_rate': attendance_rate,
            'present_count': present_count,
            'absent_count': absent_count,
            'course_stats': course_stats,
            'class_stats': class_stats
        }
    
    def _count_unique_sessions(self, records):
        """Count unique class sessions in the records"""
        if not records:
            return 0
            
        sessions = set()
        for record in records:
            # Create a unique session identifier using session_id
            sessions.add(record['session_id'])
            
        return len(sessions)
    
    def _count_unique_students(self, records):
        """Count unique students in the records"""
        if not records:
            return 0
            
        students = set(record['student_id'] for record in records)
        return len(students)
    
    def _calculate_daily_attendance(self, records):
        """Calculate attendance statistics grouped by date"""
        if not records:
            return []
            
        # Group by date
        date_groups = {}
        for record in records:
            date = record['date']
            if date not in date_groups:
                date_groups[date] = {'present': 0, 'absent': 0, 'total': 0}
            
            date_groups[date]['total'] += 1
            if record['status'] == 'Present':
                date_groups[date]['present'] += 1
            else:
                date_groups[date]['absent'] += 1
        
        # Convert to list format for charting
        attendance_data = []
        for date, stats in sorted(date_groups.items()):
            attendance_pct = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
            attendance_data.append({
                'date': date,
                'present': stats['present'],
                'absent': stats['absent'],
                'total': stats['total'],
                'attendance_pct': round(attendance_pct, 1)
            })
            
        return attendance_data
    
    def _calculate_attendance_rate(self, records):
        """Calculate overall attendance rate as percentage"""
        if not records:
            return 0
            
        present_count = sum(1 for record in records if record['status'] == 'Present')
        return round((present_count / len(records) * 100), 1) if records else 0
    
    def _calculate_course_stats(self, records):
        """Calculate attendance statistics grouped by course"""
        if not records:
            return {}
            
        course_groups = {}
        for record in records:
            course = record['course_code']
            if course not in course_groups:
                course_groups[course] = {'present': 0, 'absent': 0, 'total': 0}
            
            course_groups[course]['total'] += 1
            if record['status'] == 'Present':
                course_groups[course]['present'] += 1
            else:
                course_groups[course]['absent'] += 1
        
        # Calculate percentages
        for course, stats in course_groups.items():
            stats['attendance_pct'] = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
            stats['attendance_pct'] = round(stats['attendance_pct'], 1)
            
        return course_groups
    
    def _calculate_class_stats(self, records):
        """Calculate attendance statistics grouped by class"""
        if not records:
            return {}
            
        class_groups = {}
        for record in records:
            class_name = record['class_name']
            if class_name not in class_groups:
                class_groups[class_name] = {'present': 0, 'absent': 0, 'total': 0}
            
            class_groups[class_name]['total'] += 1
            if record['status'] == 'Present':
                class_groups[class_name]['present'] += 1
            else:
                class_groups[class_name]['absent'] += 1
        
        # Calculate percentages
        for class_name, stats in class_groups.items():
            stats['attendance_pct'] = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
            stats['attendance_pct'] = round(stats['attendance_pct'], 1)
            
        return class_groups
        
    def get_student_attendance_summary(self, student_id=None, course_code=None, start_date=None, end_date=None):
        """
        Get a summary of student attendance statistics
        
        This is a wrapper around the DatabaseService method with the same name
        
        Args:
            student_id (str, optional): Filter by student ID
            course_code (str, optional): Filter by course code
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            list: List of attendance summary records
        """
        return self.db_service.get_student_attendance_summary(
            student_id=student_id,
            course_code=course_code,
            start_date=start_date,
            end_date=end_date
        )