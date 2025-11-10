"""
Highly Optimized Dashboard Service - FIXED
Fixed cache parameter name: timeout -> ttl
"""

from datetime import datetime, date, timedelta, time
from sqlalchemy import func, and_, or_, text, case
from sqlalchemy.orm import joinedload, selectinload
from app.models import (
    ClassSession, Attendance, Student, Class, 
    Instructor, Course, Notification
)
from app import db
import logging
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

logger = logging.getLogger(__name__)


def timed_operation(operation_name):
    """Decorator to time operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time_module.time()
            result = func(*args, **kwargs)
            elapsed = time_module.time() - start
            logger.debug(f"{operation_name} took {elapsed:.3f}s")
            return result
        return wrapper
    return decorator


class DashboardService:
    """Service for dashboard data aggregation and statistics"""
    
    def __init__(self):
        self.cache = None
        try:
            from flask import current_app
            self.cache = current_app.extensions.get('cache')
        except Exception as e:
            logger.warning(f"Cache not available: {e}")
    
    @staticmethod
    def _serialize_time(time_obj):
        """Convert time object to string format HH:MM"""
        if time_obj is None:
            return None
        if isinstance(time_obj, str):
            return time_obj
        if isinstance(time_obj, (datetime, time)):
            return time_obj.strftime('%H:%M')
        return str(time_obj)
    
    @staticmethod
    def _serialize_date(date_obj):
        """Convert date object to ISO format string"""
        if date_obj is None:
            return None
        if isinstance(date_obj, str):
            return date_obj
        if isinstance(date_obj, (datetime, date)):
            return date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj)
        return str(date_obj)
    
    @staticmethod
    def _serialize_datetime(dt_obj):
        """Convert datetime object to ISO format string"""
        if dt_obj is None:
            return None
        if isinstance(dt_obj, str):
            return dt_obj
        if isinstance(dt_obj, datetime):
            return dt_obj.isoformat()
        return str(dt_obj)
    
    @timed_operation("Dashboard Full Load")
    def get_dashboard_data(self, instructor_id, date_filter=None):
        """
        Get complete dashboard data for instructor with PARALLEL execution
        
        Args:
            instructor_id: Instructor's ID
            date_filter: Optional date to filter (defaults to today)
            
        Returns:
            dict: Complete dashboard data (JSON-safe)
        """
        start_time = time_module.time()
        
        if date_filter is None:
            date_filter = date.today()
        
        logger.info(f"Loading dashboard for instructor {instructor_id}, date: {date_filter}")
        
        # Cache key
        cache_key = f"dashboard:{instructor_id}:{date_filter.isoformat()}"
        
        # TEMPORARY: Check if we should bypass cache for debugging
        force_fresh = True  # Set to False after debugging
        
        # Try to get from cache first (unless force_fresh)
        if self.cache and not force_fresh:
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached dashboard data for {instructor_id}")
                return cached_data
        
        try:
            # Get current app context to copy to threads
            from flask import current_app, copy_current_request_context
            app = current_app._get_current_object()
            
            # Wrapper to run functions with app context
            def run_with_context(func, *args, **kwargs):
                with app.app_context():
                    return func(*args, **kwargs)
            
            # PARALLEL EXECUTION - Run all queries concurrently WITH app context
            with ThreadPoolExecutor(max_workers=6) as executor:
                # Submit all tasks with app context wrapper
                future_today = executor.submit(run_with_context, self.get_today_sessions, instructor_id, date_filter)
                future_upcoming = executor.submit(run_with_context, self.get_upcoming_sessions, instructor_id, date_filter)
                future_recent = executor.submit(run_with_context, self.get_recent_sessions, instructor_id, 5)
                future_stats = executor.submit(run_with_context, self.get_statistics_optimized, instructor_id)
                future_low_att = executor.submit(run_with_context, self.get_low_attendance_students, instructor_id)
                future_perf = executor.submit(run_with_context, self.get_class_performance, instructor_id)
                
                # Collect results (blocks until all complete)
                today_sessions = future_today.result()
                upcoming_sessions = future_upcoming.result()
                recent_sessions = future_recent.result()
                statistics = future_stats.result()
                low_attendance = future_low_att.result()
                class_performance = future_perf.result()
                
                logger.info(f"Results collected: today={len(today_sessions)}, upcoming={len(upcoming_sessions)}, "
                           f"recent={len(recent_sessions)}, alerts={len(low_attendance)}")
                
                dashboard_data = {
                    'today_sessions': today_sessions,
                    'upcoming_sessions': upcoming_sessions,
                    'recent_sessions': recent_sessions,
                    'statistics': statistics,
                    'low_attendance_alerts': low_attendance,
                    'quick_stats': statistics.get('quick_stats', {}),
                    'class_performance': class_performance,
                    'notifications': self.get_recent_notifications(instructor_id, 5)
                }
            
            # Cache for 1 minute during debugging
            if self.cache:
                cache_set_result = self.cache.set(cache_key, dashboard_data, ttl=60)
                logger.info(f"Cache set result: {cache_set_result}")
            
            elapsed = time_module.time() - start_time
            logger.info(f"Dashboard loaded for {instructor_id} in {elapsed:.3f}s")
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
            raise
    
    @timed_operation("Today Sessions")
    def get_today_sessions(self, instructor_id, target_date=None):
        """Get all sessions for today - OPTIMIZED with DEBUG"""
        if target_date is None:
            target_date = date.today()
        
        target_date_str = target_date.isoformat()
        logger.info(f"Getting sessions for date: {target_date_str}")
        
        try:
            # FIRST: Check raw count
            raw_count = db.session.execute(
                text("SELECT COUNT(*) FROM class_sessions WHERE created_by = :instructor_id AND date = :date"),
                {'instructor_id': instructor_id, 'date': target_date_str}
            ).scalar()
            
            logger.info(f"Raw SQL found {raw_count} sessions for {target_date_str}")
            
            # Now get with ORM
            sessions = ClassSession.query\
                .filter(
                    ClassSession.created_by == instructor_id,
                    ClassSession.date == target_date_str
                )\
                .options(selectinload(ClassSession.class_))\
                .order_by(ClassSession.start_time)\
                .all()
            
            logger.info(f"ORM found {len(sessions)} sessions")
            
            result = []
            current_time = datetime.now().time()
            
            for session in sessions:
                try:
                    class_name = session.class_.class_name if session.class_ else 'Unknown'
                    
                    start_time_str = self._serialize_time(session.start_time)
                    end_time_str = self._serialize_time(session.end_time)
                    
                    session_data = {
                        'session_id': session.session_id,
                        'class_id': session.class_id,
                        'class_name': class_name,
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'status': session.status,
                        'attendance_count': session.attendance_count or 0,
                        'total_students': session.total_students or 0,
                        'attendance_percentage': self._calculate_percentage(
                            session.attendance_count or 0, 
                            session.total_students or 1
                        )
                    }
                    
                    # Determine session state
                    if start_time_str and end_time_str:
                        start_dt = datetime.strptime(start_time_str, '%H:%M').time()
                        end_dt = datetime.strptime(end_time_str, '%H:%M').time()
                        
                        if session.status == 'ongoing':
                            session_data['state'] = 'in_progress'
                        elif session.status == 'completed':
                            session_data['state'] = 'completed'
                        elif session.status in ['cancelled', 'dismissed']:
                            session_data['state'] = 'cancelled'
                        elif current_time < start_dt:
                            session_data['state'] = 'upcoming'
                        elif current_time > end_dt:
                            session_data['state'] = 'missed'
                        else:
                            session_data['state'] = 'ready_to_start'
                    else:
                        session_data['state'] = 'unknown'
                    
                    logger.debug(f"Session {session.session_id}: {class_name}, state={session_data['state']}, status={session.status}")
                    result.append(session_data)
                    
                except Exception as e:
                    logger.error(f"Error processing session {session.session_id}: {str(e)}")
                    continue
            
            logger.info(f"Returning {len(result)} today sessions")
            return result
            
        except Exception as e:
            logger.error(f"Error in get_today_sessions: {str(e)}", exc_info=True)
            return []
    
    @timed_operation("Upcoming Sessions")
    def get_upcoming_sessions(self, instructor_id, from_date=None, days_ahead=7):
        """Get upcoming sessions - OPTIMIZED"""
        if from_date is None:
            from_date = date.today()
        
        from_date_str = from_date.isoformat()
        end_date = from_date + timedelta(days=days_ahead)
        end_date_str = end_date.isoformat()
        
        logger.info(f"Getting upcoming sessions from {from_date_str} to {end_date_str}")
        
        try:
            sessions = ClassSession.query\
                .filter(
                    ClassSession.created_by == instructor_id,
                    ClassSession.date > from_date_str,
                    ClassSession.date <= end_date_str,
                    ClassSession.status == 'scheduled'
                )\
                .options(selectinload(ClassSession.class_))\
                .order_by(ClassSession.date, ClassSession.start_time)\
                .limit(10)\
                .all()
            
            logger.info(f"Found {len(sessions)} upcoming sessions")
            
            result = []
            for session in sessions:
                try:
                    class_name = session.class_.class_name if session.class_ else 'Unknown'
                    session_date = self._serialize_date(session.date)
                    session_date_obj = datetime.strptime(session_date, '%Y-%m-%d').date() if session_date else from_date
                    
                    result.append({
                        'session_id': session.session_id,
                        'class_id': session.class_id,
                        'class_name': class_name,
                        'date': session_date,
                        'start_time': self._serialize_time(session.start_time),
                        'end_time': self._serialize_time(session.end_time),
                        'days_until': (session_date_obj - from_date).days
                    })
                except Exception as e:
                    logger.error(f"Error processing upcoming session: {str(e)}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_upcoming_sessions: {str(e)}")
            return []

    
    
    @timed_operation("Recent Sessions")
    def get_recent_sessions(self, instructor_id, limit=5):
        """Get recently completed sessions - OPTIMIZED"""
        try:
            sessions = ClassSession.query\
                .filter(
                    ClassSession.created_by == instructor_id,
                    ClassSession.status == 'completed'
                )\
                .options(selectinload(ClassSession.class_))\
                .order_by(ClassSession.date.desc(), ClassSession.end_time.desc())\
                .limit(limit)\
                .all()
            
            logger.info(f"Found {len(sessions)} recent completed sessions")
            
            result = []
            for session in sessions:
                try:
                    class_name = session.class_.class_name if session.class_ else 'Unknown'
                    
                    result.append({
                        'session_id': session.session_id,
                        'class_id': session.class_id,
                        'class_name': class_name,
                        'date': self._serialize_date(session.date),
                        'start_time': self._serialize_time(session.start_time),
                        'end_time': self._serialize_time(session.end_time),
                        'attendance_count': session.attendance_count or 0,
                        'total_students': session.total_students or 0,
                        'attendance_percentage': self._calculate_percentage(
                            session.attendance_count or 0,
                            session.total_students or 1
                        )
                    })
                except Exception as e:
                    logger.error(f"Error processing recent session: {str(e)}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_recent_sessions: {str(e)}")
            return []
    
    @timed_operation("Statistics Optimized")
    def get_statistics_optimized(self, instructor_id, days=30):
        """
        Get comprehensive statistics - SUPER OPTIMIZED
        Combines multiple queries into ONE + quick_stats
        """
        try:
            today = date.today()
            today_str = today.isoformat()
            cutoff_date = (today - timedelta(days=days)).isoformat()
            week_start = (today - timedelta(days=today.weekday())).isoformat()
            
            logger.info(f"Getting statistics: today={today_str}, cutoff={cutoff_date}, week_start={week_start}")
            
            # MEGA OPTIMIZED: Single query for ALL stats including quick stats
            stats_query = text("""
                WITH session_stats AS (
                    SELECT 
                        COUNT(*) as total_sessions,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                        AVG(CASE 
                            WHEN status = 'completed' AND total_students > 0 
                            THEN (attendance_count * 100.0 / total_students) 
                            ELSE NULL 
                        END) as avg_attendance,
                        COUNT(DISTINCT class_id) as active_classes,
                        -- Quick stats for today
                        SUM(CASE WHEN date = :today THEN 1 ELSE 0 END) as today_total,
                        SUM(CASE WHEN date = :today AND status = 'completed' THEN 1 ELSE 0 END) as today_completed,
                        -- Quick stats for this week
                        SUM(CASE WHEN date >= :week_start AND date <= :today THEN 1 ELSE 0 END) as week_total,
                        SUM(CASE WHEN date >= :week_start AND date <= :today AND status = 'completed' THEN 1 ELSE 0 END) as week_completed
                    FROM class_sessions
                    WHERE created_by = :instructor_id AND date >= :cutoff_date
                ),
                student_stats AS (
                    SELECT COUNT(DISTINCT a.student_id) as total_students
                    FROM attendance a
                    JOIN class_sessions cs ON cs.session_id = a.session_id
                    WHERE cs.created_by = :instructor_id AND cs.date >= :cutoff_date
                )
                SELECT 
                    ss.total_sessions,
                    ss.completed_sessions,
                    COALESCE(ss.avg_attendance, 0) as avg_attendance,
                    ss.active_classes,
                    st.total_students,
                    ss.today_total,
                    ss.today_completed,
                    ss.week_total,
                    ss.week_completed
                FROM session_stats ss, student_stats st
            """)
            
            result = db.session.execute(stats_query, {
                'instructor_id': instructor_id,
                'cutoff_date': cutoff_date,
                'today': today_str,
                'week_start': week_start
            }).fetchone()
            
            if result:
                logger.info(f"Statistics result: total={result.total_sessions}, completed={result.completed_sessions}, "
                           f"today_total={result.today_total}, today_completed={result.today_completed}")
                
                stats = {
                    'total_sessions': result.total_sessions or 0,
                    'completed_sessions': result.completed_sessions or 0,
                    'completion_rate': self._calculate_percentage(
                        result.completed_sessions or 0, 
                        result.total_sessions or 1
                    ),
                    'average_attendance': round(result.avg_attendance or 0, 2),
                    'total_students': result.total_students or 0,
                    'active_classes': result.active_classes or 0,
                    'period_days': days,
                    # Include quick stats in same result
                    'quick_stats': {
                        'today': {
                            'total': result.today_total or 0,
                            'completed': result.today_completed or 0,
                            'pending': (result.today_total or 0) - (result.today_completed or 0)
                        },
                        'this_week': {
                            'total': result.week_total or 0,
                            'completed': result.week_completed or 0,
                            'completion_rate': self._calculate_percentage(
                                result.week_completed or 0,
                                result.week_total or 1
                            )
                        }
                    }
                }
            else:
                logger.warning("Statistics query returned no results!")
                stats = self._empty_stats(days)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in get_statistics_optimized: {str(e)}", exc_info=True)
            return self._empty_stats(days)
        
    
    def _empty_stats(self, days=30):
        """Return empty stats structure"""
        return {
            'total_sessions': 0,
            'completed_sessions': 0,
            'completion_rate': 0,
            'average_attendance': 0,
            'total_students': 0,
            'active_classes': 0,
            'period_days': days,
            'quick_stats': {
                'today': {'total': 0, 'completed': 0, 'pending': 0},
                'this_week': {'total': 0, 'completed': 0, 'completion_rate': 0}
            }
        }

    @timed_operation("Attendance Trend")
    def get_attendance_trend(self, instructor_id, days=7, group_by='day'):
        """
        Get attendance trend data for charts with flexible grouping
        
        Args:
            instructor_id (str): Instructor's ID
            days (int): Number of days to look back (default: 7)
            group_by (str): Grouping method - 'day', 'week', 'class' (default: 'day')
        
        Returns:
            dict: Chart-ready data with labels and values
                {
                    'labels': List of date/class labels,
                    'data': List of attendance percentages,
                    'sessions': List of session counts per data point,
                    'raw_data': Detailed breakdown for tooltips
                }
        
        Example output for 'day' grouping:
            {
                'labels': ['Nov 01', 'Nov 02', 'Nov 03', ...],
                'data': [85.5, 78.3, 91.2, ...],
                'sessions': [2, 3, 1, ...],
                'raw_data': [
                    {
                        'date': '2025-11-01',
                        'attendance': 85.5,
                        'present': 34,
                        'total': 40,
                        'sessions': 2
                    },
                    ...
                ]
            }
        """
        try:
            # Calculate cutoff date
            cutoff_date = (date.today() - timedelta(days=days)).isoformat()
            today = date.today().isoformat()
            
            logger.info(f'Getting attendance trend for {instructor_id}: {days} days, group_by={group_by}')
            
            if group_by == 'day':
                return self._get_daily_trend(instructor_id, cutoff_date, today)
            elif group_by == 'week':
                return self._get_weekly_trend(instructor_id, cutoff_date, today)
            elif group_by == 'class':
                return self._get_class_trend(instructor_id, cutoff_date, today)
            else:
                logger.warning(f'Invalid group_by parameter: {group_by}, defaulting to day')
                return self._get_daily_trend(instructor_id, cutoff_date, today)
        
        except Exception as e:
            logger.error(f'Error getting attendance trend: {str(e)}', exc_info=True)
            return {
                'labels': [],
                'data': [],
                'sessions': [],
                'raw_data': []
            }


    def _get_daily_trend(self, instructor_id, cutoff_date, today):
        """
        Get daily attendance trend
        Groups data by individual days
        """
        try:
            # Query for daily attendance aggregation
            daily_stats = db.session.query(
                ClassSession.date,
                func.count(ClassSession.session_id).label('session_count'),
                func.sum(ClassSession.attendance_count).label('total_present'),
                func.sum(ClassSession.total_students).label('total_students')
            ).filter(
                ClassSession.created_by == instructor_id,
                ClassSession.date >= cutoff_date,
                ClassSession.date <= today,
                ClassSession.status == 'completed',
                ClassSession.total_students > 0
            ).group_by(
                ClassSession.date
            ).order_by(
                ClassSession.date
            ).all()
            
            logger.info(f"Query returned {len(daily_stats)} days with data")
            
            # Format data for charts
            labels = []
            data = []
            sessions = []
            raw_data = []
            
            # Create date range to fill gaps (show 0 for days with no sessions)
            start_date = datetime.strptime(cutoff_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(today, '%Y-%m-%d').date()
            date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
            
            # Convert query results to dictionary for easy lookup
            stats_dict = {}
            for stat in daily_stats:
                # Handle date properly - could be string or date object
                if isinstance(stat.date, str):
                    date_key = stat.date
                else:
                    date_key = stat.date.isoformat() if hasattr(stat.date, 'isoformat') else str(stat.date)
                
                stats_dict[date_key] = {
                    'sessions': stat.session_count,
                    'present': stat.total_present or 0,
                    'total': stat.total_students or 0,
                    'attendance': round((stat.total_present / stat.total_students * 100), 1) if stat.total_students > 0 else 0
                }
                
                logger.debug(f"Date {date_key}: {stat.session_count} sessions, {stat.total_present}/{stat.total_students} attendance")
            
            # Fill in all dates in range
            for current_date in date_range:
                date_str = current_date.isoformat()
                date_obj = stats_dict.get(date_str, {
                    'sessions': 0,
                    'present': 0,
                    'total': 0,
                    'attendance': 0
                })
                
                # Format label based on how recent the date is
                if (end_date - current_date).days <= 7:
                    label = current_date.strftime('%a %d')  # "Mon 01"
                else:
                    label = current_date.strftime('%b %d')  # "Nov 01"
                
                labels.append(label)
                data.append(date_obj['attendance'])
                sessions.append(date_obj['sessions'])
                raw_data.append({
                    'date': date_str,
                    'attendance': date_obj['attendance'],
                    'present': date_obj['present'],
                    'total': date_obj['total'],
                    'sessions': date_obj['sessions']
                })
            
            logger.info(f'Daily trend generated: {len(labels)} data points, {sum(sessions)} total sessions')
            logger.info(f'Sample output - Labels: {labels[:3]}, Data: {data[:3]}')
            
            return {
                'labels': labels,
                'data': data,
                'sessions': sessions,
                'raw_data': raw_data
            }
        
        except Exception as e:
            logger.error(f'Error getting daily trend: {str(e)}', exc_info=True)
            return {'labels': [], 'data': [], 'sessions': [], 'raw_data': []}

    def _get_weekly_trend(self, instructor_id, cutoff_date, today):
        """
        Get weekly attendance trend
        Groups data by calendar weeks (Monday-Sunday)
        """
        try:
            # Query for weekly attendance aggregation
            weekly_stats = db.session.query(
                func.strftime('%Y-%W', ClassSession.date).label('week'),
                func.count(ClassSession.session_id).label('session_count'),
                func.sum(ClassSession.attendance_count).label('total_present'),
                func.sum(ClassSession.total_students).label('total_students'),
                func.min(ClassSession.date).label('week_start')
            ).filter(
                ClassSession.created_by == instructor_id,
                ClassSession.date >= cutoff_date,
                ClassSession.date <= today,
                ClassSession.status == 'completed',
                ClassSession.total_students > 0
            ).group_by(
                func.strftime('%Y-%W', ClassSession.date)
            ).order_by(
                'week'
            ).all()
            
            labels = []
            data = []
            sessions = []
            raw_data = []
            
            for stat in weekly_stats:
                # Parse week start date
                week_start = datetime.strptime(stat.week_start, '%Y-%m-%d')
                week_end = week_start + timedelta(days=6)
                
                # Calculate attendance percentage
                attendance_pct = round((stat.total_present / stat.total_students * 100), 1) if stat.total_students > 0 else 0
                
                # Format label: "Week of Nov 1" or "Nov 1-7"
                if week_start.month == week_end.month:
                    label = f"{week_start.strftime('%b %d')}-{week_end.strftime('%d')}"
                else:
                    label = f"{week_start.strftime('%b %d')}-{week_end.strftime('%b %d')}"
                
                labels.append(label)
                data.append(attendance_pct)
                sessions.append(stat.session_count)
                raw_data.append({
                    'week': stat.week,
                    'week_start': stat.week_start,
                    'week_end': week_end.isoformat(),
                    'attendance': attendance_pct,
                    'present': stat.total_present or 0,
                    'total': stat.total_students or 0,
                    'sessions': stat.session_count
                })
            
            logger.info(f'Weekly trend: {len(labels)} weeks, {sum(sessions)} total sessions')
            
            return {
                'labels': labels,
                'data': data,
                'sessions': sessions,
                'raw_data': raw_data
            }
        
        except Exception as e:
            logger.error(f'Error getting weekly trend: {str(e)}', exc_info=True)
            return {'labels': [], 'data': [], 'sessions': [], 'raw_data': []}


    def _get_class_trend(self, instructor_id, cutoff_date, today):
        """
        Get attendance trend by class
        Shows performance comparison across different classes
        """
        try:
            # Query for class-based attendance aggregation
            class_stats = db.session.query(
                Class.class_id,
                Class.class_name,
                func.count(ClassSession.session_id).label('session_count'),
                func.sum(ClassSession.attendance_count).label('total_present'),
                func.sum(ClassSession.total_students).label('total_students')
            ).join(
                ClassSession, Class.class_id == ClassSession.class_id
            ).filter(
                ClassSession.created_by == instructor_id,
                ClassSession.date >= cutoff_date,
                ClassSession.date <= today,
                ClassSession.status == 'completed',
                ClassSession.total_students > 0,
                Class.is_active == 1
            ).group_by(
                Class.class_id,
                Class.class_name
            ).order_by(
                func.sum(ClassSession.attendance_count).desc()  # Best performing first
            ).all()
            
            labels = []
            data = []
            sessions = []
            raw_data = []
            
            for stat in class_stats:
                # Calculate attendance percentage
                attendance_pct = round((stat.total_present / stat.total_students * 100), 1) if stat.total_students > 0 else 0
                
                # Truncate long class names for labels
                class_name = stat.class_name
                if len(class_name) > 25:
                    class_name = class_name[:22] + '...'
                
                labels.append(class_name)
                data.append(attendance_pct)
                sessions.append(stat.session_count)
                raw_data.append({
                    'class_id': stat.class_id,
                    'class_name': stat.class_name,
                    'attendance': attendance_pct,
                    'present': stat.total_present or 0,
                    'total': stat.total_students or 0,
                    'sessions': stat.session_count,
                    'avg_per_session': round(attendance_pct / stat.session_count, 1) if stat.session_count > 0 else 0
                })
            
            logger.info(f'Class trend: {len(labels)} classes, {sum(sessions)} total sessions')
            
            return {
                'labels': labels,
                'data': data,
                'sessions': sessions,
                'raw_data': raw_data
            }
        
        except Exception as e:
            logger.error(f'Error getting class trend: {str(e)}', exc_info=True)
            return {'labels': [], 'data': [], 'sessions': [], 'raw_data': []}


    @timed_operation("Attendance Comparison")
    def get_attendance_comparison(self, instructor_id, days=30):
        """
        Get multi-dimensional attendance comparison
        Compares current period vs previous period
        
        Returns:
            dict: Comparison data with trends
        """
        try:
            current_end = date.today()
            current_start = current_end - timedelta(days=days)
            previous_start = current_start - timedelta(days=days)
            
            # Current period stats
            current_stats = db.session.query(
                func.count(ClassSession.session_id).label('sessions'),
                func.avg(
                    (ClassSession.attendance_count * 100.0) / 
                    func.nullif(ClassSession.total_students, 0)
                ).label('avg_attendance')
            ).filter(
                ClassSession.created_by == instructor_id,
                ClassSession.date >= current_start.isoformat(),
                ClassSession.date <= current_end.isoformat(),
                ClassSession.status == 'completed',
                ClassSession.total_students > 0
            ).first()
            
            # Previous period stats
            previous_stats = db.session.query(
                func.count(ClassSession.session_id).label('sessions'),
                func.avg(
                    (ClassSession.attendance_count * 100.0) / 
                    func.nullif(ClassSession.total_students, 0)
                ).label('avg_attendance')
            ).filter(
                ClassSession.created_by == instructor_id,
                ClassSession.date >= previous_start.isoformat(),
                ClassSession.date < current_start.isoformat(),
                ClassSession.status == 'completed',
                ClassSession.total_students > 0
            ).first()
            
            # Calculate changes
            current_attendance = round(current_stats.avg_attendance or 0, 1)
            previous_attendance = round(previous_stats.avg_attendance or 0, 1)
            
            attendance_change = round(current_attendance - previous_attendance, 1)
            attendance_change_pct = round(
                (attendance_change / previous_attendance * 100) if previous_attendance > 0 else 0,
                1
            )
            
            return {
                'current': {
                    'attendance': current_attendance,
                    'sessions': current_stats.sessions or 0,
                    'period': f'{current_start.strftime("%b %d")} - {current_end.strftime("%b %d")}'
                },
                'previous': {
                    'attendance': previous_attendance,
                    'sessions': previous_stats.sessions or 0,
                    'period': f'{previous_start.strftime("%b %d")} - {(current_start - timedelta(days=1)).strftime("%b %d")}'
                },
                'change': {
                    'absolute': attendance_change,
                    'percentage': attendance_change_pct,
                    'direction': 'up' if attendance_change > 0 else 'down' if attendance_change < 0 else 'stable',
                    'is_improving': attendance_change >= 0
                }
            }
        
        except Exception as e:
            logger.error(f'Error getting attendance comparison: {str(e)}', exc_info=True)
            return None


    @timed_operation("Peak Attendance Times")
    def get_peak_attendance_times(self, instructor_id, days=30):
        """
        Analyze which times of day have best/worst attendance
        
        Returns:
            dict: Time-based attendance analysis
        """
        try:
            cutoff_date = (date.today() - timedelta(days=days)).isoformat()
            
            # Group by hour of day
            time_stats = db.session.query(
                func.substr(ClassSession.start_time, 1, 2).label('hour'),
                func.count(ClassSession.session_id).label('sessions'),
                func.avg(
                    (ClassSession.attendance_count * 100.0) / 
                    func.nullif(ClassSession.total_students, 0)
                ).label('avg_attendance')
            ).filter(
                ClassSession.created_by == instructor_id,
                ClassSession.date >= cutoff_date,
                ClassSession.status == 'completed',
                ClassSession.total_students > 0
            ).group_by(
                'hour'
            ).order_by(
                'hour'
            ).all()
            
            # Format results
            time_periods = {
                'morning': {'hours': ['07', '08', '09', '10', '11'], 'attendance': [], 'sessions': 0},
                'afternoon': {'hours': ['12', '13', '14', '15', '16'], 'attendance': [], 'sessions': 0},
                'evening': {'hours': ['17', '18', '19', '20', '21'], 'attendance': [], 'sessions': 0}
            }
            
            hourly_data = []
            
            for stat in time_stats:
                hour = stat.hour
                attendance = round(stat.avg_attendance or 0, 1)
                
                # Add to hourly breakdown
                hourly_data.append({
                    'hour': f'{hour}:00',
                    'attendance': attendance,
                    'sessions': stat.sessions
                })
                
                # Categorize into time periods
                for period, config in time_periods.items():
                    if hour in config['hours']:
                        config['attendance'].append(attendance)
                        config['sessions'] += stat.sessions
            
            # Calculate period averages
            for period in time_periods.values():
                if period['attendance']:
                    period['avg_attendance'] = round(sum(period['attendance']) / len(period['attendance']), 1)
                else:
                    period['avg_attendance'] = 0
            
            return {
                'hourly': hourly_data,
                'periods': {
                    'morning': {
                        'attendance': time_periods['morning']['avg_attendance'],
                        'sessions': time_periods['morning']['sessions']
                    },
                    'afternoon': {
                        'attendance': time_periods['afternoon']['avg_attendance'],
                        'sessions': time_periods['afternoon']['sessions']
                    },
                    'evening': {
                        'attendance': time_periods['evening']['avg_attendance'],
                        'sessions': time_periods['evening']['sessions']
                    }
                }
            }
        
        except Exception as e:
            logger.error(f'Error getting peak attendance times: {str(e)}', exc_info=True)
            return None
    
    @timed_operation("Low Attendance Students")
    def get_low_attendance_students(self, instructor_id, threshold=75, limit=10):
        """Get students with low attendance - HEAVILY OPTIMIZED"""
        try:
            cutoff_date = (date.today() - timedelta(days=30)).isoformat()
            
            query = text("""
                SELECT 
                    s.student_id,
                    s.fname,
                    s.lname,
                    cs.class_id,
                    COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as attended,
                    COUNT(cs.session_id) as total,
                    (COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 100.0 / COUNT(cs.session_id)) as percentage
                FROM students s
                JOIN attendance a ON a.student_id = s.student_id
                JOIN class_sessions cs ON cs.session_id = a.session_id
                WHERE cs.created_by = :instructor_id 
                    AND cs.status = 'completed'
                    AND cs.date >= :cutoff_date
                GROUP BY s.student_id, s.fname, s.lname, cs.class_id
                HAVING percentage < :threshold
                ORDER BY percentage ASC
                LIMIT :limit
            """)
            
            results = db.session.execute(query, {
                'instructor_id': instructor_id,
                'cutoff_date': cutoff_date,
                'threshold': threshold,
                'limit': limit
            }).fetchall()
            
            logger.info(f"Found {len(results)} low attendance students")
            
            low_attendance = [
                {
                    'student_id': row.student_id,
                    'student_name': f"{row.fname} {row.lname}",
                    'class_id': row.class_id,
                    'attended': row.attended,
                    'total': row.total,
                    'percentage': round(row.percentage, 2),
                    'risk_level': self._get_risk_level(row.percentage)
                }
                for row in results
            ]
            
            return low_attendance
            
        except Exception as e:
            logger.error(f"Error in get_low_attendance_students: {str(e)}", exc_info=True)
            return []
    
    @timed_operation("Class Performance")
    def get_class_performance(self, instructor_id, limit=10):
        """Get performance overview - OPTIMIZED"""
        try:
            cutoff_date = (date.today() - timedelta(days=30)).isoformat()
            
            query = text("""
                SELECT 
                    cs.class_id,
                    c.class_name,
                    COUNT(cs.session_id) as total_sessions,
                    SUM(cs.attendance_count) as total_present,
                    SUM(cs.total_students) as total_possible
                FROM class_sessions cs
                JOIN classes c ON c.class_id = cs.class_id
                WHERE cs.created_by = :instructor_id
                    AND cs.status = 'completed'
                    AND cs.date >= :cutoff_date
                GROUP BY cs.class_id, c.class_name
                ORDER BY total_sessions DESC
                LIMIT :limit
            """)
            
            results = db.session.execute(query, {
                'instructor_id': instructor_id,
                'cutoff_date': cutoff_date,
                'limit': limit
            }).fetchall()
            
            logger.info(f"Found {len(results)} class performance records")
            
            result = []
            for stat in results:
                avg_attendance = (stat.total_present / stat.total_possible * 100) if stat.total_possible > 0 else 0
                result.append({
                    'class_id': stat.class_id,
                    'class_name': stat.class_name,
                    'total_sessions': stat.total_sessions,
                    'average_attendance': round(avg_attendance, 2),
                    'performance_status': self._get_performance_status(avg_attendance)
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_class_performance: {str(e)}")
            return []
    
    def get_recent_notifications(self, instructor_id, limit=5):
        """Get recent notifications"""
        try:
            notifications = Notification.query\
                .filter(
                    Notification.user_id == instructor_id,
                    Notification.user_type == 'instructor'
                )\
                .order_by(Notification.created_at.desc())\
                .limit(limit)\
                .all()
            
            result = [
                {
                    'id': notif.id,
                    'title': notif.title,
                    'message': notif.message,
                    'type': notif.type,
                    'is_read': notif.is_read,
                    'created_at': self._serialize_datetime(notif.created_at),
                    'action_url': notif.action_url,
                    'priority': notif.priority
                }
                for notif in notifications
            ]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_recent_notifications: {str(e)}")
            return []
    
    def invalidate_cache(self, instructor_id):
        """Invalidate all cached data for an instructor"""
        if self.cache:
            try:
                # Simple approach: delete specific keys
                today = date.today()
                cache_key = f"dashboard:{instructor_id}:{today.isoformat()}"
                self.cache.delete(cache_key)
                logger.info(f"Cache invalidated for instructor {instructor_id}")
            except Exception as e:
                logger.error(f"Error invalidating cache: {e}")
    
    # Helper methods
    def _calculate_percentage(self, part, whole):
        """Calculate percentage safely"""
        if whole == 0:
            return 0.0
        return round((part / whole) * 100, 2)
    
    def _get_risk_level(self, percentage):
        """Determine risk level based on attendance percentage"""
        if percentage < 50:
            return 'critical'
        elif percentage < 65:
            return 'high'
        elif percentage < 75:
            return 'medium'
        else:
            return 'low'
    
    def _get_performance_status(self, percentage):
        """Determine performance status based on attendance"""
        if percentage >= 90:
            return 'excellent'
        elif percentage >= 80:
            return 'good'
        elif percentage >= 70:
            return 'fair'
        elif percentage >= 60:
            return 'poor'
        else:
            return 'critical'