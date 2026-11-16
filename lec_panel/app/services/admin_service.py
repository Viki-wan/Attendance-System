"""
Admin Service
Campus-wide dashboard stats and general admin orchestration.
No instructor_id filtering anywhere in this file -- admin sees all data.
"""

from datetime import date, timedelta
import logging

from app.models import (
    Student, Instructor, Course, Class, ClassSession, ActivityLog
)
from app import db

logger = logging.getLogger(__name__)


class AdminService:
    """Service for admin dashboard data aggregation."""

    def get_dashboard_stats(self):
        """
        Get campus-wide dashboard stats: entity counts, today's sessions,
        and recent activity across all users (instructors + admins).

        Returns:
            dict: JSON-safe dashboard data for the admin dashboard template.
        """
        try:
            today_str = date.today().isoformat()

            total_students = Student.query.count()
            total_lecturers = Instructor.query.count()
            total_courses = Course.query.count()
            total_classes = Class.query.filter(Class.is_active == 1).count()

            today_sessions_count = ClassSession.query.filter(
                ClassSession.date == today_str
            ).count()

            today_completed = ClassSession.query.filter(
                ClassSession.date == today_str,
                ClassSession.status == 'completed'
            ).count()

            recent_activity = self.get_recent_activity(limit=10)

            return {
                'stats': {
                    'total_students': total_students,
                    'total_lecturers': total_lecturers,
                    'total_courses': total_courses,
                    'total_classes': total_classes,
                    'today_sessions': today_sessions_count,
                    'today_completed': today_completed,
                },
                'recent_activity': recent_activity,
            }

        except Exception as e:
            logger.error(f'Error building admin dashboard stats: {str(e)}', exc_info=True)
            return {
                'stats': {
                    'total_students': 0,
                    'total_lecturers': 0,
                    'total_courses': 0,
                    'total_classes': 0,
                    'today_sessions': 0,
                    'today_completed': 0,
                },
                'recent_activity': [],
            }

    def get_recent_activity(self, limit=10):
        """
        Get the most recent activity log entries campus-wide
        (both instructor and admin actions).

        Args:
            limit (int): Max number of entries to return.

        Returns:
            list[ActivityLog]: Most recent entries, newest first.
        """
        try:
            return ActivityLog.query \
                .order_by(ActivityLog.timestamp.desc()) \
                .limit(limit) \
                .all()
        except Exception as e:
            logger.error(f'Error fetching recent activity: {str(e)}')
            return []