"""
API Blueprint for AJAX endpoints and real-time data
Handles dashboard widgets, attendance updates, and system diagnostics
"""
from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime, timedelta
import json
from lecturer_panel.utils.decorators import login_required
from lecturer_panel.utils.helpers import get_current_user, log_error
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.services.attendance_service import AttendanceService
from lecturer_panel.services.diagnostics_service import DiagnosticsService
from lecturer_panel.services.notification_service import NotificationService

api_bp = Blueprint('api', __name__)

# Initialize services
db_service = DatabaseService()
attendance_service = AttendanceService()
diagnostics_service = DiagnosticsService()
notification_service = NotificationService()

@api_bp.route('/dashboard/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    """Get real-time dashboard statistics"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        instructor_id = user['instructor_id']
        stats = attendance_service.get_dashboard_stats(instructor_id)
        return jsonify(stats)
    except Exception as e:
        log_error(f"Error getting dashboard stats: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to get dashboard stats'}), 500

@api_bp.route('/attendance/session/<int:session_id>', methods=['GET'])
@login_required
def get_session_attendance(session_id):
    """Get real-time attendance data for a session"""
    try:
        result = attendance_service.get_session_attendance(session_id)
        if not result:
            return jsonify({'error': 'Session not found'}), 404
        return jsonify(result)
    except Exception as e:
        log_error(f"Error getting session attendance: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to get session attendance'}), 500

@api_bp.route('/attendance/mark', methods=['POST'])
@login_required
def mark_attendance():
    """Mark attendance for a student"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        student_id = data.get('student_id')
        status = data.get('status', 'Present')
        method = data.get('method', 'manual')
        if not all([session_id, student_id]):
            return jsonify({'error': 'Missing required fields'}), 400
        user = get_current_user()
        instructor_id = user['instructor_id']
        result = attendance_service.mark_attendance(
            student_id=student_id,
            session_id=session_id,
            status=status,
            marked_by=instructor_id,
            method=method
        )
        if result['success']:
            attendance_service.update_session_count(session_id)
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('attendance_update', {
                    'session_id': session_id,
                    'student_id': student_id,
                    'status': status,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            return jsonify({'success': True, 'message': 'Attendance marked successfully'})
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        log_error(f"Error marking attendance: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to mark attendance'}), 500

@api_bp.route('/attendance/bulk-mark', methods=['POST'])
@login_required
def bulk_mark_attendance():
    """Mark attendance for multiple students"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        student_ids = data.get('student_ids', [])
        status = data.get('status', 'Present')
        if not all([session_id, student_ids]):
            return jsonify({'error': 'Missing required fields'}), 400
        user = get_current_user()
        instructor_id = user['instructor_id']
        result = attendance_service.bulk_mark_attendance(
            session_id=session_id,
            student_ids=student_ids,
            status=status,
            marked_by=instructor_id
        )
        if result['success']:
            attendance_service.update_session_count(session_id)
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('bulk_attendance_update', {
                    'session_id': session_id,
                    'success_count': result.get('success_count', 0),
                    'failed_count': result.get('failed_count', 0)
                })
            return jsonify({'success': True, 'message': result['message']})
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        log_error(f"Error bulk marking attendance: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to bulk mark attendance'}), 500

@api_bp.route('/session/start', methods=['POST'])
@login_required
def start_session():
    """Start an attendance session"""
    try:
        data = request.get_json()
        class_id = data.get('class_id')
        if not class_id:
            return jsonify({'error': 'Class ID is required'}), 400
        user = get_current_user()
        instructor_id = user['instructor_id']
        result = attendance_service.start_session(class_id, instructor_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        log_error(f"Error starting session: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to start session'}), 500

@api_bp.route('/session/end/<int:session_id>', methods=['POST'])
@login_required
def end_session(session_id):
    """End an attendance session"""
    try:
        user = get_current_user()
        instructor_id = user['instructor_id']
        result = attendance_service.end_session(session_id, instructor_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        log_error(f"Error ending session: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to end session'}), 500

@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get notifications for current user"""
    try:
        user = get_current_user()
        instructor_id = user['instructor_id']
        notifications = notification_service.get_user_notifications(str(instructor_id), 'instructor')
        return jsonify({'notifications': notifications})
    except Exception as e:
        log_error(f"Error getting notifications: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to get notifications'}), 500

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        user = get_current_user()
        instructor_id = user['instructor_id']
        result = notification_service.mark_notification_read(notification_id, str(instructor_id))
        if result['success']:
            return jsonify({'success': True})
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        log_error(f"Error marking notification as read: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to mark notification as read'}), 500

@api_bp.route('/diagnostics/camera', methods=['GET'])
@login_required
def get_camera_diagnostics():
    """Get camera diagnostics information"""
    try:
        diagnostics = diagnostics_service.get_camera_diagnostics()
        return jsonify(diagnostics)
    except Exception as e:
        log_error(f"Error getting camera diagnostics: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to get camera diagnostics'}), 500

@api_bp.route('/diagnostics/system', methods=['GET'])
@login_required
def get_system_diagnostics():
    """Get system diagnostics information"""
    try:
        diagnostics = diagnostics_service.get_system_diagnostics()
        return jsonify(diagnostics)
    except Exception as e:
        log_error(f"Error getting system diagnostics: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to get system diagnostics'}), 500

@api_bp.route('/settings/preferences', methods=['GET', 'POST'])
@login_required
def handle_preferences():
    """Get or update lecturer preferences"""
    try:
        user = get_current_user()
        instructor_id = user['instructor_id']
        if request.method == 'GET':
            preferences = db_service.get_lecturer_preferences(instructor_id)
            return jsonify(preferences)
        elif request.method == 'POST':
            data = request.get_json()
            result = db_service.update_lecturer_preferences(instructor_id, data)
            if result:
                return jsonify({'success': True, 'message': 'Preferences updated successfully'})
            else:
                return jsonify({'error': 'Failed to update preferences'}), 400
    except Exception as e:
        log_error(f"Error handling preferences: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to handle preferences'}), 500

def log_activity(user_id, user_type, activity_type, description):
    """Log user activity"""
    try:
        db_service.log_activity(user_id, user_type, activity_type, description)
    except Exception as e:
        log_error(f"Error logging activity: {str(e)}", "ACTIVITY_LOG_ERROR")

@api_bp.route('/events/attendance-update', methods=['POST'])
@login_required
def emit_attendance_update():
    """Emit real-time attendance update"""
    try:
        data = request.get_json()
        if hasattr(current_app, 'socketio'):
            current_app.socketio.emit('attendance_update', data)
        return jsonify({'success': True})
    except Exception as e:
        log_error(f"Error emitting attendance update: {str(e)}", "API_ERROR")
        return jsonify({'error': 'Failed to emit update'}), 500