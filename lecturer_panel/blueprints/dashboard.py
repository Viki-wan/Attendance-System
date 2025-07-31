from flask import Blueprint, render_template, session, jsonify
from lecturer_panel.services import dashboard_service

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    user_id = session.get('user_id')
    stats = dashboard_service.get_dashboard_stats(user_id)
    sessions = dashboard_service.get_sessions(user_id)
    activity_feed = dashboard_service.get_activity_feed(user_id)
    attendance_summary = dashboard_service.get_attendance_summary(user_id)
    camera_status = dashboard_service.get_camera_status(user_id)
    return render_template(
        'dashboard/index.html',
        stats=stats,
        sessions=sessions,
        activity_feed=activity_feed,
        attendance_summary=attendance_summary,
        camera_status=camera_status
    )

@dashboard_bp.route('/data')
def dashboard_data():
    user_id = session.get('user_id')
    stats = dashboard_service.get_dashboard_stats(user_id)
    sessions = dashboard_service.get_sessions(user_id)
    activity_feed = dashboard_service.get_activity_feed(user_id)
    attendance_summary = dashboard_service.get_attendance_summary(user_id)
    camera_status = dashboard_service.get_camera_status(user_id)
    return jsonify({
        'stats': stats,
        'sessions': sessions,
        'activity_feed': activity_feed,
        'attendance_summary': attendance_summary,
        'camera_status': camera_status
    }) 