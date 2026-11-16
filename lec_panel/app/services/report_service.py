"""
Report Service - Business logic for generating various reports
Handles data aggregation, statistics calculation, and report preparation
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, case
from app.models import (
    ClassSession, Attendance, Student, Class, Course, 
    Instructor, StudentCourse
)
from app import db
import pandas as pd
from collections import defaultdict


class ReportService:
    """Service for generating attendance reports and analytics"""
    
    def __init__(self):
        self.date_format = '%Y-%m-%d'
        self.time_format = '%H:%M'
        self.datetime_format = '%Y-%m-%d %H:%M:%S'
    
    # ========== Session Reports ==========
    
    def generate_session_summary(self, session_id, instructor_id):
        """
        Generate detailed summary for a single session
        
        Args:
            session_id: Session ID
            instructor_id: Instructor ID for ownership validation
            
        Returns:
            dict: Session summary data
        """
        session = ClassSession.query.get(session_id)
        
        if not session:
            return None
        
        # Ownership validation - use correct method name
        if not session.can_be_accessed_by(instructor_id):
            return None
        
        # Get attendance records
        attendance_records = Attendance.query.filter_by(
            session_id=session_id
        ).all()
        
        # Calculate statistics
        total_expected = len(session.class_.students)
        present_count = sum(1 for a in attendance_records if a.status == 'Present')
        late_count = sum(1 for a in attendance_records if a.status == 'Late')
        absent_count = sum(1 for a in attendance_records if a.status == 'Absent')
        excused_count = sum(1 for a in attendance_records if a.status == 'Excused')
        
        attendance_rate = (present_count + late_count) / total_expected * 100 if total_expected > 0 else 0
        
        # Get recognition method breakdown
        face_recognition_count = sum(
            1 for a in attendance_records 
            if a.method == 'face_recognition' and a.status == 'Present'
        )
        manual_count = sum(
            1 for a in attendance_records 
            if a.method == 'manual' and a.status == 'Present'
        )
        
        # Build student list with status
        students_data = []
        for student in session.class_.students:
            attendance = next(
                (a for a in attendance_records if a.student_id == student.student_id), 
                None
            )
            
            students_data.append({
                'student_id': student.student_id,
                'name': f"{student.fname} {student.lname}",
                'email': student.email,
                'status': attendance.status if attendance else 'Absent',
                'timestamp': attendance.timestamp.strftime(self.datetime_format) if attendance else None,
                'method': attendance.method if attendance else None,
                'confidence': attendance.confidence_score if attendance else None,
                'notes': attendance.notes if attendance else None
            })
        
        return {
            'session_info': {
                'session_id': session.session_id,
                'class_id': session.class_id,
                'class_name': session.class_.class_name,
                'course_code': session.class_.course_code,
                'course_name': session.class_.course.course_name,
                'date': session.date.strftime(self.date_format) if session.date else None,
                'start_time': session.start_time.strftime(self.time_format) if session.start_time else None,
                'end_time': session.end_time.strftime(self.time_format) if session.end_time else None,
                'status': session.status,
                'notes': session.session_notes
            },
            'statistics': {
                'total_expected': total_expected,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'attendance_rate': round(attendance_rate, 2),
                'face_recognition_marked': face_recognition_count,
                'manually_marked': manual_count
            },
            'students': students_data,
            'generated_at': datetime.now().strftime(self.datetime_format)
        }
    
    def generate_class_summary(self, class_id, instructor_id, start_date=None, end_date=None):
        """
        Generate summary report for all sessions of a class
        
        Args:
            class_id: Class ID
            instructor_id: Instructor ID
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            
        Returns:
            dict: Class summary data
        """
        # Validate ownership - use correct method name
        class_ = Class.query.get(class_id)
        if not class_ or not class_.is_assigned_to(instructor_id):
            return None
        
        # Build query
        query = ClassSession.query.filter_by(class_id=class_id)
        
        if start_date:
            query = query.filter(ClassSession.date >= start_date)
        if end_date:
            query = query.filter(ClassSession.date <= end_date)
        
        sessions = query.order_by(ClassSession.date.desc()).all()
        
        # Aggregate statistics
        total_sessions = len(sessions)
        completed_sessions = sum(1 for s in sessions if s.status == 'completed')
        
        all_attendance = []
        for session in sessions:
            all_attendance.extend(session.attendance_records)
        
        total_present = sum(1 for a in all_attendance if a.status == 'Present')
        total_late = sum(1 for a in all_attendance if a.status == 'Late')
        total_absent = sum(1 for a in all_attendance if a.status == 'Absent')
        
        avg_attendance_rate = (
            sum(s.attendance_count / s.total_students * 100 for s in sessions if s.total_students > 0) 
            / total_sessions
        ) if total_sessions > 0 else 0
        
        # Build session summaries
        session_summaries = []
        for session in sessions:
            session_summaries.append({
                'session_id': session.session_id,
                'date': session.date.strftime(self.date_format) if session.date else None,
                'start_time': session.start_time.strftime(self.time_format) if session.start_time else None,
                'end_time': session.end_time.strftime(self.time_format) if session.end_time else None,
                'status': session.status,
                'attendance_count': session.attendance_count,
                'total_students': session.total_students,
                'attendance_rate': (
                    session.attendance_count / session.total_students * 100 
                    if session.total_students > 0 else 0
                )
            })
        
        # Student-wise attendance summary
        students_summary = self._calculate_student_attendance_summary(
            class_.students, 
            sessions
        )
        
        # Calculate students at risk (attendance < 75%)
        students_at_risk = sum(1 for s in students_summary if s['attendance_rate'] < 75)
        
        return {
            'class_info': {
                'class_id': class_.class_id,
                'class_name': class_.class_name,
                'course_code': class_.course_code,
                'course_name': class_.course.course_name,
                'year': class_.year,
                'semester': class_.semester,
                'total_students': len(class_.students)
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions
            },
            'statistics': {
                'total_students': len(class_.students),
                'total_sessions': total_sessions,
                'total_present': total_present,
                'total_late': total_late,
                'total_absent': total_absent,
                'average_attendance': round(avg_attendance_rate, 2),
                'students_at_risk': students_at_risk
            },
            'sessions': session_summaries,
            'students': students_summary,
            'generated_at': datetime.now().strftime(self.datetime_format)
        }
    
    # ========== Student Reports ==========
    
    def generate_student_report(self, student_id, class_id, instructor_id):
        """
        Generate attendance report for a specific student in a class
        
        Args:
            student_id: Student ID
            class_id: Class ID
            instructor_id: Instructor ID
            
        Returns:
            dict: Student attendance report
        """
        # Validate ownership - use correct method name
        class_ = Class.query.get(class_id)
        if not class_ or not class_.is_assigned_to(instructor_id):
            return None
        
        student = Student.query.get(student_id)
        if not student:
            return None
        
        # Get all sessions for the class
        sessions = ClassSession.query.filter_by(class_id=class_id).all()
        
        # Get student's attendance records
        attendance_records = Attendance.query.filter_by(
            student_id=student_id
        ).join(ClassSession).filter(
            ClassSession.class_id == class_id
        ).all()
        
        # Calculate statistics
        total_sessions = len(sessions)
        present_count = sum(1 for a in attendance_records if a.status == 'Present')
        late_count = sum(1 for a in attendance_records if a.status == 'Late')
        absent_count = sum(1 for a in attendance_records if a.status == 'Absent')
        excused_count = sum(1 for a in attendance_records if a.status == 'Excused')
        
        attendance_rate = (present_count + late_count) / total_sessions * 100 if total_sessions > 0 else 0
        
        # Build attendance history
        attendance_history = []
        for session in sessions:
            attendance = next(
                (a for a in attendance_records if a.session_id == session.session_id),
                None
            )
            
            attendance_history.append({
                'session_id': session.session_id,
                'date': session.date.strftime(self.date_format) if session.date else None,
                'start_time': session.start_time.strftime(self.time_format) if session.start_time else None,
                'end_time': session.end_time.strftime(self.time_format) if session.end_time else None,
                'status': attendance.status if attendance else 'Absent',
                'timestamp': attendance.timestamp.strftime(self.datetime_format) if attendance else None,
                'method': attendance.method if attendance else None,
                'notes': attendance.notes if attendance else None
            })
        
        return {
            'student_info': {
                'student_id': student.student_id,
                'name': f"{student.fname} {student.lname}",
                'email': student.email,
                'phone': student.phone,
                'course': student.course,
                'year': student.year_of_study,
                'semester': student.current_semester
            },
            'class_info': {
                'class_id': class_.class_id,
                'class_name': class_.class_name,
                'course_code': class_.course_code,
                'course_name': class_.course.course_name
            },
            'statistics': {
                'total_sessions': total_sessions,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'attendance_rate': round(attendance_rate, 2)
            },
            'attendance_history': attendance_history,
            'generated_at': datetime.now().strftime(self.datetime_format)
        }
    
    # ========== Trend Analysis ==========
    
    def generate_trend_analysis(self, class_id, instructor_id, days=30):
        """
        Generate attendance trend analysis over time
        
        Args:
            class_id: Class ID
            instructor_id: Instructor ID
            days: Number of days to analyze
            
        Returns:
            dict: Trend analysis data
        """
        # Validate ownership - use correct method name
        class_ = Class.query.get(class_id)
        if not class_ or not class_.is_assigned_to(instructor_id):
            return None
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get sessions in date range
        sessions = ClassSession.query.filter(
            and_(
                ClassSession.class_id == class_id,
                ClassSession.date >= start_date.strftime(self.date_format),
                ClassSession.date <= end_date.strftime(self.date_format)
            )
        ).order_by(ClassSession.date).all()
        
        # Build trend data
        daily_data = []
        for session in sessions:
            attendance_rate = (
                session.attendance_count / session.total_students * 100 
                if session.total_students > 0 else 0
            )
            
            daily_data.append({
                'date': session.date.strftime(self.date_format) if session.date else None,
                'session_id': session.session_id,
                'attendance_rate': round(attendance_rate, 2),
                'present': session.attendance_count,
                'total': session.total_students
            })
        
        # Calculate moving average
        if len(daily_data) >= 3:
            for i in range(2, len(daily_data)):
                avg = sum(
                    daily_data[j]['attendance_rate'] 
                    for j in range(i-2, i+1)
                ) / 3
                daily_data[i]['moving_average'] = round(avg, 2)
        
        # Identify trends
        trend_direction = 'stable'
        if len(daily_data) >= 2:
            recent_avg = sum(d['attendance_rate'] for d in daily_data[-5:]) / min(5, len(daily_data))
            overall_avg = sum(d['attendance_rate'] for d in daily_data) / len(daily_data)
            
            if recent_avg > overall_avg + 5:
                trend_direction = 'improving'
            elif recent_avg < overall_avg - 5:
                trend_direction = 'declining'
        
        return {
            'class_info': {
                'class_id': class_.class_id,
                'class_name': class_.class_name,
                'course_name': class_.course.course_name
            },
            'period': {
                'start_date': start_date.strftime(self.date_format),
                'end_date': end_date.strftime(self.date_format),
                'days': days
            },
            'trend': {
                'direction': trend_direction,
                'data': daily_data
            },
            'generated_at': datetime.now().strftime(self.datetime_format)
        }
    
    # ========== Alert Reports ==========
    
    def generate_low_attendance_alert(self, instructor_id, threshold=75):
        """
        Generate alert for students with low attendance
        
        Args:
            instructor_id: Instructor ID
            threshold: Attendance percentage threshold (default 75%)
            
        Returns:
            dict: Low attendance alert data
        """
        # Get all classes for instructor
        instructor = Instructor.query.get(instructor_id)
        if not instructor:
            return None
        
        classes = instructor.classes
        
        at_risk_students = []
        
        for class_ in classes:
            # Get all sessions for this class
            sessions = ClassSession.query.filter_by(class_id=class_.class_id).all()
            total_sessions = len(sessions)
            
            if total_sessions == 0:
                continue
            
            # Check each student
            for student in class_.students:
                attendance_count = Attendance.query.filter(
                    and_(
                        Attendance.student_id == student.student_id,
                        Attendance.session_id.in_([s.session_id for s in sessions]),
                        or_(
                            Attendance.status == 'Present',
                            Attendance.status == 'Late'
                        )
                    )
                ).count()
                
                attendance_rate = (attendance_count / total_sessions * 100) if total_sessions > 0 else 0
                
                if attendance_rate < threshold:
                    at_risk_students.append({
                        'student_id': student.student_id,
                        'name': f"{student.fname} {student.lname}",
                        'email': student.email,
                        'class_id': class_.class_id,
                        'class_name': class_.class_name,
                        'course_code': class_.course_code,
                        'total_sessions': total_sessions,
                        'attended': attendance_count,
                        'attendance_rate': round(attendance_rate, 2),
                        'sessions_missed': total_sessions - attendance_count
                    })
        
        # Sort by attendance rate (lowest first)
        at_risk_students.sort(key=lambda x: x['attendance_rate'])
        
        return {
            'alert_info': {
                'threshold': threshold,
                'total_at_risk': len(at_risk_students),
                'instructor_id': instructor_id,
                'instructor_name': instructor.instructor_name
            },
            'students': at_risk_students,
            'generated_at': datetime.now().strftime(self.datetime_format)
        }
    
    # ========== Helper Methods ==========
    
    def _calculate_student_attendance_summary(self, students, sessions):
        """Calculate attendance summary for each student"""
        summary = []
        total_sessions = len(sessions)
        
        for student in students:
            attendance_records = [
                a for session in sessions 
                for a in session.attendance_records 
                if a.student_id == student.student_id
            ]
            
            present = sum(1 for a in attendance_records if a.status == 'Present')
            late = sum(1 for a in attendance_records if a.status == 'Late')
            absent = sum(1 for a in attendance_records if a.status == 'Absent')
            
            attendance_rate = (present + late) / total_sessions * 100 if total_sessions > 0 else 0
            
            summary.append({
                'student_id': student.student_id,
                'name': f"{student.fname} {student.lname}",
                'email': student.email,
                'present': present,
                'late': late,
                'absent': absent,
                'attendance_rate': round(attendance_rate, 2)
            })
        
        # Sort by attendance rate (lowest first)
        summary.sort(key=lambda x: x['attendance_rate'])
        
        return summary
    
    def export_to_dataframe(self, data, report_type):
        """
        Convert report data to pandas DataFrame for export
        
        Args:
            data: Report data dictionary
            report_type: Type of report
            
        Returns:
            pd.DataFrame: Data in DataFrame format
        """
        if report_type == 'session_summary':
            return pd.DataFrame(data['students'])
        
        elif report_type == 'class_summary':
            return pd.DataFrame(data['students'])
        
        elif report_type == 'student_report':
            return pd.DataFrame(data['attendance_history'])
        
        elif report_type == 'low_attendance':
            return pd.DataFrame(data['students'])
        
        elif report_type == 'trend_analysis':
            return pd.DataFrame(data['trend']['data'])
        
        return pd.DataFrame()