"""
Lecturer Dashboard Routes
Main dashboard with statistics, quick actions, and session overview
Enhanced with caching, better error handling, and real-time features
"""

from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from functools import wraps
import logging
import traceback

from app.services.dashboard_service import DashboardService
from app.services.session_service import SessionService
from app.decorators.auth import active_account_required
from app.models import ClassSession, Class, Student, Attendance, ActivityLog
from app import db

# Configure logging
logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/lecturer/dashboard')


def log_activity(activity_type):
    """Decorator to log user activities"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                log = ActivityLog(
                    user_id=current_user.instructor_id,
                    user_type='instructor',
                    activity_type=activity_type,
                    description=f'{activity_type} action performed',
                    timestamp=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
            except Exception as e:
                logger.error(f'Failed to log activity: {e}')
            return result
        return decorated_function
    return decorator


@dashboard_bp.route('/')
@login_required
@active_account_required
@log_activity('dashboard_view')
def index():
    """Main dashboard view - FIXED"""
    dashboard_service = DashboardService()
    
    try:
        logger.info(f'Step 1: Starting dashboard load for {current_user.instructor_id}')
        
        # Force refresh if requested
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        if force_refresh:
            logger.info('Force refresh requested - invalidating cache')
            dashboard_service.invalidate_cache(current_user.instructor_id)
        
        # Get complete dashboard data
        dashboard_data = dashboard_service.get_dashboard_data(
            instructor_id=current_user.instructor_id
        )
        
        logger.info(f'Step 2: Dashboard data loaded')
        logger.info(f'Dashboard keys: {dashboard_data.keys() if dashboard_data else "None"}')
        
        # DEBUG: Log actual data values
        if dashboard_data:
            logger.info(f'Quick stats: {dashboard_data.get("quick_stats")}')
            logger.info(f'Statistics: {dashboard_data.get("statistics")}')
            logger.info(f'Today sessions count: {len(dashboard_data.get("today_sessions", []))}')
            logger.info(f'Low attendance alerts count: {len(dashboard_data.get("low_attendance_alerts", []))}')
        
        # Get instructor's classes
        logger.info(f'Step 3: Loading instructor classes')
        instructor_classes = db.session.query(Class)\
            .join(ClassSession, Class.class_id == ClassSession.class_id)\
            .filter(
                ClassSession.created_by == current_user.instructor_id,
                Class.is_active == 1
            )\
            .distinct()\
            .all()
        
        logger.info(f'Step 4: Found {len(instructor_classes)} classes')
        
        # SAFETY CHECK: Ensure all required keys exist
        if dashboard_data:
            # Ensure quick_stats exists and has required structure
            if 'quick_stats' not in dashboard_data or not dashboard_data['quick_stats']:
                logger.warning('quick_stats missing or empty, using default')
                dashboard_data['quick_stats'] = {
                    'today': {'total': 0, 'completed': 0, 'pending': 0},
                    'this_week': {'total': 0, 'completed': 0, 'completion_rate': 0}
                }
            
            # Ensure today stats exist
            if 'today' not in dashboard_data['quick_stats']:
                dashboard_data['quick_stats']['today'] = {'total': 0, 'completed': 0, 'pending': 0}
            
            # Ensure statistics exist
            if 'statistics' not in dashboard_data or not dashboard_data['statistics']:
                logger.warning('statistics missing or empty, using default')
                dashboard_data['statistics'] = {
                    'total_sessions': 0,
                    'completed_sessions': 0,
                    'completion_rate': 0,
                    'average_attendance': 0,
                    'active_classes': 0
                }
        
        logger.info(f'Dashboard loaded successfully for instructor {current_user.instructor_id}')
        
        return render_template(
            'lecturer/dashboard.html',
            dashboard=dashboard_data,
            classes=instructor_classes,
            current_date=date.today(),
            current_user=current_user
        )
    
    except Exception as e:
        logger.error(f'Error loading dashboard: {str(e)}', exc_info=True)
        flash(f'Error loading dashboard. Please try again later.', 'error')
        
        # Return with empty but valid structure
        empty_dashboard = {
            'today_sessions': [],
            'upcoming_sessions': [],
            'recent_sessions': [],
            'statistics': {
                'total_sessions': 0,
                'completed_sessions': 0,
                'completion_rate': 0,
                'average_attendance': 0,
                'active_classes': 0
            },
            'low_attendance_alerts': [],
            'quick_stats': {
                'today': {'total': 0, 'completed': 0, 'pending': 0},
                'this_week': {'total': 0, 'completed': 0, 'completion_rate': 0}
            },
            'class_performance': [],
            'notifications': []
        }
        
        return render_template(
            'lecturer/dashboard.html', 
            dashboard=empty_dashboard,
            classes=[],
            current_date=date.today(),
            current_user=current_user
        )


@dashboard_bp.route('/refresh')
@login_required
@active_account_required
def refresh_data():
    """Force refresh dashboard data by invalidating cache"""
    dashboard_service = DashboardService()
    
    try:
        # Invalidate cache first
        dashboard_service.invalidate_cache(current_user.instructor_id)
        logger.info(f'Cache invalidated for instructor {current_user.instructor_id}')
        
        # Get fresh data
        dashboard_data = dashboard_service.get_dashboard_data(
            instructor_id=current_user.instructor_id
        )
        
        return jsonify({
            'success': True,
            'data': {
                'today_sessions': dashboard_data.get('today_sessions', []),
                'quick_stats': dashboard_data.get('quick_stats', {}),
                'low_attendance_alerts': dashboard_data.get('low_attendance_alerts', [])[:5],
                'recent_sessions': dashboard_data.get('recent_sessions', [])[:3],
                'timestamp': datetime.now().isoformat()
            },
            'message': 'Dashboard refreshed successfully'
        })
    
    except Exception as e:
        logger.error(f'Error refreshing dashboard: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to refresh dashboard data'}), 500


@dashboard_bp.route('/clear-cache')
@login_required
@active_account_required
def clear_cache():
    """Clear all cache for current instructor - DEBUG ONLY"""
    dashboard_service = DashboardService()
    
    try:
        dashboard_service.invalidate_cache(current_user.instructor_id)
        flash('Cache cleared successfully. Dashboard will reload with fresh data.', 'success')
        logger.info(f'Cache manually cleared for instructor {current_user.instructor_id}')
        return redirect(url_for('dashboard.index', refresh='true'))
    
    except Exception as e:
        logger.error(f'Error clearing cache: {str(e)}')
        flash('Error clearing cache', 'error')
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/debug-data')
@login_required
@active_account_required
def debug_data():
    """DEBUG ROUTE: View raw dashboard data - Remove in production"""
    dashboard_service = DashboardService()
    
    try:
        # Get fresh data (bypass cache)
        dashboard_service.invalidate_cache(current_user.instructor_id)
        dashboard_data = dashboard_service.get_dashboard_data(
            instructor_id=current_user.instructor_id
        )
        
        # Return as JSON for easy viewing
        return jsonify({
            'instructor_id': current_user.instructor_id,
            'data': dashboard_data,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500


@dashboard_bp.route('/statistics')
@login_required
@active_account_required
@log_activity('statistics_view')
def statistics():
    """
    Detailed statistics view with ALL analytics features
    - Daily/Weekly/Class trends
    - Period comparison
    - Peak attendance times
    - Class performance
    """
    dashboard_service = DashboardService()
    
    # Get parameters from query string
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 7), 365)  # Clamp between 7 and 365 days
    
    group_by = request.args.get('group_by', 'day')  # day, week, or class
    
    try:
        logger.info(f'Loading statistics for {current_user.instructor_id}: {days} days, group_by={group_by}')
        
        # Get core statistics
        stats = dashboard_service.get_statistics_optimized(
            current_user.instructor_id, 
            days=days
        )
        
        # Get class performance data
        class_performance = dashboard_service.get_class_performance(
            current_user.instructor_id
        )
        
        # Get attendance trend data (Daily/Weekly/By Class)
        trend_data = dashboard_service.get_attendance_trend(
            current_user.instructor_id,
            days=days,
            group_by=group_by
        )
        
        # Get comparison data (current vs previous period)
        comparison_data = dashboard_service.get_attendance_comparison(
            current_user.instructor_id,
            days=days
        )
        
        # Get peak attendance times analysis
        peak_times = dashboard_service.get_peak_attendance_times(
            current_user.instructor_id,
            days=days
        )
        
        # DEBUG: Log what we got
        logger.info(f'Statistics loaded:')
        logger.info(f'  - Trend points: {len(trend_data.get("labels", []))}')
        logger.info(f'  - Classes: {len(class_performance)}')
        logger.info(f'  - Comparison available: {comparison_data is not None}')
        logger.info(f'  - Peak times available: {peak_times is not None}')
        
        # Ensure safe defaults for all data
        if not trend_data or not trend_data.get('labels'):
            logger.warning('No trend data available')
            trend_data = {'labels': [], 'data': [], 'sessions': [], 'raw_data': []}
        
        if not comparison_data:
            logger.warning('No comparison data available')
            comparison_data = {
                'current': {'attendance': 0, 'sessions': 0, 'period': 'N/A'},
                'previous': {'attendance': 0, 'sessions': 0, 'period': 'N/A'},
                'change': {'absolute': 0, 'percentage': 0, 'direction': 'stable', 'is_improving': False}
            }
        
        if not peak_times:
            logger.warning('No peak times data available')
            peak_times = {
                'hourly': [],
                'periods': {
                    'morning': {'attendance': 0, 'sessions': 0},
                    'afternoon': {'attendance': 0, 'sessions': 0},
                    'evening': {'attendance': 0, 'sessions': 0}
                }
            }
        
        if not class_performance:
            class_performance = []
        else:
            # Sort by attendance (best first)
            class_performance = sorted(
                class_performance, 
                key=lambda x: x.get('average_attendance', 0), 
                reverse=True
            )
        
        logger.info(f'Statistics page ready with all analytics')
        
        return render_template(
            'lecturer/statistics.html',
            statistics=stats,
            class_performance=class_performance,
            selected_period=days,
            group_by=group_by,
            trend_data=trend_data,
            comparison_data=comparison_data,
            peak_times=peak_times,
            current_user=current_user
        )
    
    except Exception as e:
        logger.error(f'Error loading statistics: {str(e)}', exc_info=True)
        flash('Error loading statistics. Please try again.', 'error')
        
        # Return with safe empty structure
        return render_template(
            'lecturer/statistics.html',
            statistics={
                'total_sessions': 0,
                'completed_sessions': 0,
                'completion_rate': 0,
                'average_attendance': 0,
                'active_classes': 0,
                'total_students': 0,
                'period_days': days
            },
            class_performance=[],
            selected_period=days,
            group_by='day',
            trend_data={'labels': [], 'data': [], 'sessions': [], 'raw_data': []},
            comparison_data={
                'current': {'attendance': 0, 'sessions': 0, 'period': 'N/A'},
                'previous': {'attendance': 0, 'sessions': 0, 'period': 'N/A'},
                'change': {'absolute': 0, 'percentage': 0, 'direction': 'stable', 'is_improving': False}
            },
            peak_times={
                'hourly': [],
                'periods': {
                    'morning': {'attendance': 0, 'sessions': 0},
                    'afternoon': {'attendance': 0, 'sessions': 0},
                    'evening': {'attendance': 0, 'sessions': 0}
                }
            },
            current_user=current_user
        )


@dashboard_bp.route('/statistics/export')
@login_required
@active_account_required
@log_activity('statistics_export')
def export_statistics():
    """
    Export detailed statistics in various formats
    """
    dashboard_service = DashboardService()
    
    days = request.args.get('days', 30, type=int)
    format_type = request.args.get('format', 'pdf').lower()
    
    try:
        # Gather all statistics data
        stats = dashboard_service.get_statistics_optimized(
            current_user.instructor_id, 
            days=days
        )
        class_performance = dashboard_service.get_class_performance(
            current_user.instructor_id
        )
        trend_data = dashboard_service.get_attendance_trend(
            current_user.instructor_id,
            days=days,
            group_by='day'
        )
        comparison_data = dashboard_service.get_attendance_comparison(
            current_user.instructor_id,
            days=days
        )
        
        export_data = {
            'instructor_name': current_user.instructor_name,
            'instructor_id': current_user.instructor_id,
            'period_days': days,
            'generated_at': datetime.now(),
            'statistics': stats,
            'class_performance': class_performance,
            'trend_data': trend_data,
            'comparison': comparison_data
        }
        
        if format_type == 'pdf':
            from app.utils.pdf_generator import generate_statistics_pdf
            return generate_statistics_pdf(export_data)
        
        elif format_type == 'excel':
            from app.utils.excel_generator import generate_statistics_excel
            return generate_statistics_excel(export_data)
        
        elif format_type == 'csv':
            from app.utils.csv_generator import generate_statistics_csv
            return generate_statistics_csv(export_data)
        
        elif format_type == 'json':
            return jsonify({
                'success': True,
                'data': export_data
            })
        
        else:
            flash('Invalid export format', 'error')
            return redirect(url_for('dashboard.statistics'))
    
    except Exception as e:
        logger.error(f'Error exporting statistics: {str(e)}', exc_info=True)
        flash('Error exporting statistics', 'error')
        return redirect(url_for('dashboard.statistics'))

@dashboard_bp.route('/quick-start/<class_id>')
@login_required
@active_account_required
@log_activity('quick_start_session')
def quick_start_session(class_id):
    """
    Quick start attendance session from dashboard
    Redirects to attendance marking interface
    """
    try:
        # Verify class ownership
        class_obj = Class.query.filter_by(class_id=class_id).first_or_404()
        
        # Check if instructor has permission for this class
        has_permission = db.session.query(ClassSession).filter(
            ClassSession.class_id == class_id,
            ClassSession.created_by == current_user.instructor_id
        ).first() is not None
        
        if not has_permission:
            flash('You do not have permission to start sessions for this class', 'error')
            return redirect(url_for('dashboard.index'))
        
        # Check if there's an ongoing session for this class today
        today = date.today()
        existing_session = ClassSession.query\
            .filter(
                ClassSession.class_id == class_id,
                ClassSession.created_by == current_user.instructor_id,
                ClassSession.date == today.isoformat(),
                ClassSession.status == 'ongoing'
            )\
            .first()
        
        if existing_session:
            flash('Session already in progress', 'info')
            return redirect(url_for('attendance.live_attendance', 
                                   session_id=existing_session.session_id))
        
        # Check if there's a scheduled session
        scheduled_session = ClassSession.query\
            .filter(
                ClassSession.class_id == class_id,
                ClassSession.created_by == current_user.instructor_id,
                ClassSession.date == today.isoformat(),
                ClassSession.status == 'scheduled'
            )\
            .first()
        
        if scheduled_session:
            # Start the scheduled session
            scheduled_session.status = 'ongoing'
            scheduled_session.updated_at = datetime.now()
            db.session.commit()
            
            # Invalidate cache after session update
            dashboard_service = DashboardService()
            dashboard_service.invalidate_cache(current_user.instructor_id)
            
            logger.info(f'Started scheduled session {scheduled_session.session_id}')
            flash('Session started successfully', 'success')
            return redirect(url_for('attendance.live_attendance', 
                                   session_id=scheduled_session.session_id))
        
        # Create new session with default times
        current_time = datetime.now()
        new_session = ClassSession(
            class_id=class_id,
            date=today.isoformat(),
            start_time=current_time.strftime('%H:%M'),
            end_time=(current_time + timedelta(hours=1, minutes=30)).strftime('%H:%M'),
            status='ongoing',
            created_by=current_user.instructor_id,
            created_at=datetime.now(),
            session_notes='Quick-started from dashboard'
        )
        
        # Get total students for this class
        total_students = db.session.query(db.func.count(db.func.distinct(Student.student_id)))\
            .join('courses')\
            .join(Class, Class.course_code == Student.course)\
            .filter(Class.class_id == class_id)\
            .scalar() or 0
        
        new_session.total_students = total_students
        
        db.session.add(new_session)
        db.session.commit()
        
        # Invalidate cache after creating new session
        dashboard_service = DashboardService()
        dashboard_service.invalidate_cache(current_user.instructor_id)
        
        logger.info(f'Created new quick-start session {new_session.session_id}')
        flash('New session started successfully', 'success')
        return redirect(url_for('attendance.live_attendance', 
                               session_id=new_session.session_id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error starting session for class {class_id}: {str(e)}')
        flash(f'Error starting session. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/session/<int:session_id>/end', methods=['POST'])
@login_required
@active_account_required
@log_activity('end_session')
def end_session(session_id):
    """
    Quick end session from dashboard
    """
    try:
        session = ClassSession.query.get_or_404(session_id)
        
        # Verify ownership
        if session.created_by != current_user.instructor_id:
            return jsonify({
                'success': False, 
                'error': 'Unauthorized'
            }), 403
        
        # Check if session is already completed
        if session.status == 'completed':
            return jsonify({
                'success': False,
                'error': 'Session already completed'
            }), 400
        
        # Update session status
        session.status = 'completed'
        session.updated_at = datetime.now()
        
        # Update attendance count
        attendance_count = Attendance.query.filter_by(
            session_id=session_id,
            status='Present'
        ).count()
        session.attendance_count = attendance_count
        
        db.session.commit()
        
        # Invalidate cache after ending session
        dashboard_service = DashboardService()
        dashboard_service.invalidate_cache(current_user.instructor_id)
        
        logger.info(f'Session {session_id} ended by instructor {current_user.instructor_id}')
        
        return jsonify({
            'success': True,
            'message': 'Session ended successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error ending session {session_id}: {str(e)}')
        return jsonify({
            'success': False, 
            'error': 'Failed to end session'
        }), 500


@dashboard_bp.route('/api/chart-data/<chart_type>')
@login_required
@active_account_required
def get_chart_data(chart_type):
    """
    API endpoint for chart data
    Returns JSON data for various chart types
    """
    dashboard_service = DashboardService()
    
    try:
        if chart_type == 'attendance_trend':
            days = request.args.get('days', 7, type=int)
            days = min(max(days, 7), 90)  # Clamp between 7 and 90 days
            
            data = dashboard_service.get_attendance_trend(
                current_user.instructor_id, 
                days=days
            )
            return jsonify({'success': True, 'data': data})
        
        elif chart_type == 'class_performance':
            performance = dashboard_service.get_class_performance(
                current_user.instructor_id
            )
            
            # Format for chart
            chart_data = {
                'labels': [p['class_name'] for p in performance],
                'data': [p['average_attendance'] for p in performance],
                'colors': [
                    '#27ae60' if p.get('performance_status') == 'excellent'
                    else '#3498db' if p.get('performance_status') == 'good'
                    else '#f39c12' if p.get('performance_status') == 'fair'
                    else '#e74c3c'
                    for p in performance
                ]
            }
            return jsonify({'success': True, 'data': chart_data})
        
        elif chart_type == 'weekly_overview':
            stats = dashboard_service.get_statistics_optimized(current_user.instructor_id)
            chart_data = {
                'labels': ['Completed', 'Pending'],
                'data': [
                    stats.get('quick_stats', {}).get('this_week', {}).get('completed', 0),
                    stats.get('quick_stats', {}).get('this_week', {}).get('total', 0) - 
                    stats.get('quick_stats', {}).get('this_week', {}).get('completed', 0)
                ],
                'colors': ['#27ae60', '#e74c3c']
            }
            return jsonify({'success': True, 'data': chart_data})
        
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid chart type'
            }), 400
    
    except Exception as e:
        logger.error(f'Error getting chart data: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Failed to load chart data'
        }), 500


@dashboard_bp.route('/alerts')
@login_required
@active_account_required
@log_activity('alerts_view')
def low_attendance_alerts():
    """
    View all low attendance alerts
    """
    dashboard_service = DashboardService()
    
    threshold = request.args.get('threshold', 75, type=int)
    threshold = min(max(threshold, 50), 100)  # Clamp between 50 and 100
    
    try:
        alerts = dashboard_service.get_low_attendance_students(
            current_user.instructor_id,
            threshold=threshold,
            limit=100
        )
        
        return render_template(
            'lecturer/alerts.html',
            alerts=alerts,
            threshold=threshold
        )
    
    except Exception as e:
        logger.error(f'Error loading alerts: {str(e)}')
        flash(f'Error loading alerts. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/notifications')
@login_required
@active_account_required
def notifications():
    """
    View all notifications with pagination and filtering
    """
    from app.models import Notification
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    filter_type = request.args.get('filter', 'all')
    check_new = request.args.get('check_new', 'false').lower() == 'true'
    
    try:
        # Handle check for new notifications (AJAX request)
        if check_new:
            unread_count = Notification.get_unread_count(
                current_user.instructor_id,
                'instructor'
            )
            return jsonify({
                'has_new': unread_count > 0,
                'count': unread_count
            })
        
        # Build query
        notifications_query = Notification.query.filter_by(
            user_id=current_user.instructor_id,
            user_type='instructor'
        ).filter(
            db.or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.now()
            )
        )
        
        # Apply filters
        if filter_type == 'unread':
            notifications_query = notifications_query.filter_by(is_read=0)
        elif filter_type == 'urgent':
            notifications_query = notifications_query.filter_by(priority='urgent')
        
        # Order by unread first, then by creation date
        notifications_query = notifications_query.order_by(
            Notification.is_read.asc(),
            Notification.created_at.desc()
        )
        
        # Paginate
        notifications_paginated = notifications_query.paginate(
            page=page, 
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'lecturer/notifications.html',
            notifications=notifications_paginated,
            current_user=current_user
        )
    
    except Exception as e:
        logger.error(f'Error loading notifications: {str(e)}', exc_info=True)
        flash('Error loading notifications', 'error')
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/notifications/<int:notification_id>/mark-read', methods=['POST'])
@login_required
@active_account_required
def mark_notification_read(notification_id):
    """
    Mark notification as read
    """
    from app.models import Notification
    
    try:
        notification = Notification.query.get_or_404(notification_id)
        
        # Verify ownership
        if notification.user_id != current_user.instructor_id:
            return jsonify({
                'success': False, 
                'error': 'Unauthorized'
            }), 403
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error marking notification as read: {str(e)}')
        return jsonify({
            'success': False, 
            'error': 'Failed to mark notification as read'
        }), 500


@dashboard_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
@active_account_required
def mark_all_notifications_read():
    """
    Mark all notifications as read
    """
    from app.models import Notification
    
    try:
        Notification.query.filter_by(
            user_id=current_user.instructor_id,
            user_type='instructor',
            is_read=False
        ).update({'is_read': True})
        
        db.session.commit()
        
        flash('All notifications marked as read', 'success')
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error marking all notifications as read: {str(e)}')
        return jsonify({
            'success': False, 
            'error': 'Failed to mark notifications as read'
        }), 500

@dashboard_bp.route('/notifications/<int:notification_id>/mark-unread', methods=['POST'])
@login_required
@active_account_required
def mark_notification_unread(notification_id):
    """
    Mark notification as unread
    """
    from app.models import Notification
    
    try:
        notification = Notification.query.get_or_404(notification_id)
        
        # Verify ownership
        if notification.user_id != current_user.instructor_id:
            return jsonify({
                'success': False, 
                'error': 'Unauthorized'
            }), 403
        
        notification.mark_as_unread()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error marking notification as unread: {str(e)}')
        return jsonify({
            'success': False, 
            'error': 'Failed to mark notification as unread'
        }), 500

@dashboard_bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
@active_account_required
def delete_notification(notification_id):
    """
    Delete a notification
    """
    from app.models import Notification
    
    try:
        notification = Notification.query.get_or_404(notification_id)
        
        # Verify ownership
        if notification.user_id != current_user.instructor_id:
            return jsonify({
                'success': False, 
                'error': 'Unauthorized'
            }), 403
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting notification: {str(e)}')
        return jsonify({
            'success': False, 
            'error': 'Failed to delete notification'
        }), 500



@dashboard_bp.route('/welcome')
@login_required
@active_account_required
def welcome():
    """
    Welcome/onboarding page for new instructors
    """
    try:
        # Check if instructor has any sessions
        has_sessions = ClassSession.query\
            .filter_by(created_by=current_user.instructor_id)\
            .first() is not None
        
        if has_sessions:
            # Already onboarded, redirect to main dashboard
            return redirect(url_for('dashboard.index'))
        
        # Get instructor's assigned classes
        instructor_classes = db.session.query(Class)\
            .join(ClassSession, Class.class_id == ClassSession.class_id)\
            .filter(
                ClassSession.created_by == current_user.instructor_id,
                Class.is_active == 1
            )\
            .distinct()\
            .all()
        
        return render_template(
            'lecturer/welcome.html',
            classes=instructor_classes
        )
    
    except Exception as e:
        logger.error(f'Error loading welcome page: {str(e)}')
        flash('Error loading welcome page', 'error')
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/export-summary')
@login_required
@active_account_required
@log_activity('export_summary')
def export_summary():
    """
    Export dashboard summary as PDF or Excel
    """
    from app.utils.pdf_generator import generate_dashboard_pdf
    from app.utils.excel_generator import generate_dashboard_excel
    
    export_format = request.args.get('format', 'pdf').lower()
    dashboard_service = DashboardService()
    
    try:
        dashboard_data = dashboard_service.get_dashboard_data(
            current_user.instructor_id
        )
        
        if export_format == 'pdf':
            pdf_file = generate_dashboard_pdf(
                dashboard_data,
                current_user.instructor_name
            )
            return pdf_file
        
        elif export_format == 'excel':
            excel_file = generate_dashboard_excel(
                dashboard_data,
                current_user.instructor_name
            )
            return excel_file
        
        else:
            flash('Invalid export format', 'error')
            return redirect(url_for('dashboard.index'))
    
    except Exception as e:
        logger.error(f'Error exporting dashboard summary: {str(e)}')
        flash('Error exporting dashboard summary', 'error')
        return redirect(url_for('dashboard.index'))