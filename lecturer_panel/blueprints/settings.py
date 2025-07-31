from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from lecturer_panel.utils.decorators import login_required
from lecturer_panel.utils.helpers import get_current_user
from lecturer_panel.services.database_service import DatabaseService
import json

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/')
@login_required
def index():
    """Main settings page"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    # Get current preferences
    preferences = db.get_lecturer_preferences(instructor_id)
    
    # Get system settings
    system_settings = db.get_system_settings()
    
    # Get notification settings
    notification_settings = json.loads(preferences.get('notification_settings', '{}'))
    
    return render_template('settings/index.html', 
                         preferences=preferences,
                         system_settings=system_settings,
                         notification_settings=notification_settings)

@settings_bp.route('/theme', methods=['POST'])
@login_required
def update_theme():
    """Update theme preference"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    theme = request.json.get('theme', 'light')
    
    if theme not in ['light', 'dark']:
        return jsonify({'error': 'Invalid theme'}), 400
    
    try:
        db.update_lecturer_preference(instructor_id, 'theme', theme)
        return jsonify({'success': True, 'theme': theme})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/dashboard-layout', methods=['POST'])
@login_required
def update_dashboard_layout():
    """Update dashboard layout preference"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    layout = request.json.get('layout', 'default')
    
    try:
        db.update_lecturer_preference(instructor_id, 'dashboard_layout', layout)
        return jsonify({'success': True, 'layout': layout})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/notifications', methods=['POST'])
@login_required
def update_notifications():
    """Update notification settings"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    notification_settings = {
        'email_enabled': request.json.get('email_enabled', False),
        'push_enabled': request.json.get('push_enabled', False),
        'session_reminders': request.json.get('session_reminders', True),
        'attendance_alerts': request.json.get('attendance_alerts', True),
        'system_notifications': request.json.get('system_notifications', True),
        'low_attendance_threshold': request.json.get('low_attendance_threshold', 70),
        'reminder_time_minutes': request.json.get('reminder_time_minutes', 15)
    }
    
    try:
        db.update_lecturer_preference(instructor_id, 'notification_settings', 
                                    json.dumps(notification_settings))
        return jsonify({'success': True, 'settings': notification_settings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/session-defaults', methods=['POST'])
@login_required
def update_session_defaults():
    """Update session default settings"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    try:
        auto_refresh = int(request.json.get('auto_refresh_interval', 30))
        session_duration = int(request.json.get('default_session_duration', 90))
        
        db.update_lecturer_preference(instructor_id, 'auto_refresh_interval', auto_refresh)
        db.update_lecturer_preference(instructor_id, 'default_session_duration', session_duration)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/face-recognition', methods=['POST'])
@login_required
def update_face_recognition():
    """Update face recognition settings (system-wide)"""
    db = DatabaseService()
    
    # Only allow if user has admin privileges
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        threshold = float(request.json.get('face_recognition_threshold', 0.6))
        if threshold < 0.3 or threshold > 0.9:
            return jsonify({'error': 'Threshold must be between 0.3 and 0.9'}), 400
            
        db.update_system_setting('face_recognition_threshold', str(threshold))
        return jsonify({'success': True, 'threshold': threshold})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/attendance-rules', methods=['POST'])
@login_required
def update_attendance_rules():
    """Update attendance marking rules"""
    db = DatabaseService()
    
    try:
        late_threshold = int(request.json.get('auto_mark_late_threshold', 10))
        max_duration = int(request.json.get('max_session_duration', 180))
        
        db.update_system_setting('auto_mark_late_threshold', str(late_threshold))
        db.update_system_setting('max_session_duration', str(max_duration))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Update lecturer profile"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    if request.method == 'GET':
        instructor = db.get_instructor_by_id(instructor_id)
        return render_template('settings/profile.html', instructor=instructor)
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        faculty = request.form.get('faculty')
        
        db.update_instructor_profile(instructor_id, name, email, phone, faculty)
        flash('Profile updated successfully', 'success')
        
        return redirect(url_for('settings.profile'))
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
        return redirect(url_for('settings.profile'))

@settings_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change lecturer password"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect(url_for('settings.profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('settings.profile'))
    
    try:
        if db.verify_instructor_password(instructor_id, current_password):
            db.update_instructor_password(instructor_id, new_password)
            flash('Password changed successfully', 'success')
        else:
            flash('Current password is incorrect', 'error')
    except Exception as e:
        flash(f'Error changing password: {str(e)}', 'error')
    
    return redirect(url_for('settings.profile'))

@settings_bp.route('/reset-preferences', methods=['POST'])
@login_required
def reset_preferences():
    """Reset all preferences to default"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    try:
        db.reset_lecturer_preferences(instructor_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/export-data', methods=['POST'])
@login_required
def export_data():
    """Export lecturer data"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    
    try:
        data = db.export_lecturer_data(instructor_id)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/timezone', methods=['POST'])
@login_required
def update_timezone():
    """Update timezone preference"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    timezone = request.json.get('timezone', 'UTC')
    
    try:
        db.update_lecturer_preference(instructor_id, 'timezone', timezone)
        return jsonify({'success': True, 'timezone': timezone})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/language', methods=['POST'])
@login_required
def update_language():
    """Update language preference"""
    db = DatabaseService()
    instructor_id = session.get('user_id')
    language = request.json.get('language', 'en')
    
    try:
        db.update_lecturer_preference(instructor_id, 'language', language)
        return jsonify({'success': True, 'language': language})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/preferences')
@login_required
def preferences():
    """Lecturer preferences page (placeholder)"""
    return render_template('settings/preferences.html')